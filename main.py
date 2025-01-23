import json
import time
import uuid
from fastapi import FastAPI, HTTPException, File, UploadFile
from pydantic import BaseModel
import boto3
from decouple import config

# AWS configuration
AWS_REGION = config("AWS_REGION")
AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY")
BUCKET_NAME = config("AWS_BUCKET_NAME")

# Initialize Boto3 Bedrock client
bedrock_runtime = boto3.client(
    "bedrock-runtime",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)

# Initialize FastAPI app
app = FastAPI()


# Request model
class PromptRequest(BaseModel):
    model_id: str = "amazon.titan-text-lite-v1"
    prompt: str


# API endpoint
@app.post("/generate")
async def generate_response(request: PromptRequest):
    try:
        kwargs = {
            "modelId": request.model_id,
            "contentType": "application/json",
            "accept": "*/*",
            "body": json.dumps({"inputText": request.prompt}),
        }
        # Call AWS Bedrock
        response = bedrock_runtime.invoke_model(**kwargs)
        # Parse response
        response_body = json.loads(response.get("body").read())
        result = response_body["results"][0]["outputText"]
        return {"response": result}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error invoking Bedrock: {str(e)}",
        )


async def upload_file_to_s3(file_obj, file_name, s3_client):

    try:
        s3_client.Bucket(BUCKET_NAME).put_object(Key=file_name, Body=file_obj)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"File uplaod failed: {e}",
        )


async def transcribe_audio(bucket_name, file_name, file_content):

    # Upload Audio to s3 bucket
    s3_client = boto3.resource("s3")
    await upload_file_to_s3(
        file_obj=file_content, file_name=file_name, s3_client=s3_client
    )

    transcribe_client = boto3.client("transcribe", region_name="us")

    job_name = f"transcription-job-{uuid.uuid4()}"

    response = transcribe_client.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={"MediaFileUri": f"s3://{bucket_name}/{file_name}"},
        MediaFormat="mp3",
        LanguageCode="en-US",
        OutputBucketName=bucket_name,
        Settings={"ShowSpeakerLabels": True, "MaxSpeakerLabels": 2},
    )

    while True:
        status = transcribe_client.get_transcription_job(
            TranscriptionJobName=job_name,
        )
        if status["TranscriptionJob"]["TranscriptionJobStatus"] in [
            "COMPLETED",
            "FAILED",
        ]:
            break
        time.sleep(2)

    print(status["TranscriptionJob"]["TranscriptionJobStatus"])

    if status["TranscriptionJob"]["TranscriptionJobStatus"] == "COMPLETED":

        # Load the transcript from S3.
        transcript_key = f"{job_name}.json"
        transcript_obj = s3_client.get_object(
            Bucket=bucket_name,
            Key=transcript_key,
        )
        transcript_text = transcript_obj["Body"].read().decode("utf-8")
        transcript_json = json.loads(transcript_text)

        output_text = ""
        current_speaker = None

        items = transcript_json["results"]["items"]

        for item in items:

            speaker_label = item.get("speaker_label", None)
            content = item["alternatives"][0]["content"]

            # Start the line with the speaker label:
            if speaker_label is not None and speaker_label != current_speaker:
                current_speaker = speaker_label
                output_text += f"\n{current_speaker}: "

            # Add the speech content:
            if item["type"] == "punctuation":
                output_text = output_text.rstrip()

            output_text += f"{content} "

        # Save the transcript to a text file
        with open(f"{job_name}.txt", "w") as f:
            f.write(output_text)

    return output_text


@app.post("/summary")
async def audio_summary(file: UploadFile = File(...)):
    file_content = await file.read()

    response = await transcribe_audio(
        bucket_name=BUCKET_NAME,
        filename=file.filename,
        file_content=file_content,
    )

    return {"response": response}
