import json
import time
import uuid
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import boto3
from decouple import config


AWS_REGION = config("AWS_REGION")
AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY")
BUCKET_NAME = config("AWS_BUCKET_NAME")
OUTPUT_BUCKET_NAME = config("OUTPUT_BUCKET_NAME")


app = FastAPI()

# Configure allowed origins
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")


async def upload_file_to_s3(file_obj, file_name, s3_client, bucket_name):

    try:
        s3_client.upload_fileobj(file_obj, bucket_name, file_name)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"File uplaod failed: {e}",
        )


async def summarize_transcription(model_id: str, transcript: str):

    bedrock_runtime = boto3.client(
        "bedrock-runtime",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )

    template = templates.get_template("prompt_template.txt")

    rendered_prompt = template.render(transcript=transcript)

    try:
        kwargs = {
            "modelId": model_id,
            "contentType": "application/json",
            "accept": "*/*",
            "body": json.dumps(
                {
                    "inputText": rendered_prompt,
                    "textGenerationConfig": {
                        "maxTokenCount": 512,
                        "temperature": 0,
                        "topP": 0.9,
                    },
                }
            ),
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


def process_transcription(transcript_json):
    output_text = ""
    current_speaker = None

    items = transcript_json["results"]["items"]

    for item in items:

        speaker_label = item.get("speaker_label", None)
        content = item["alternatives"][0]["content"]

        if speaker_label is not None and speaker_label != current_speaker:
            current_speaker = speaker_label
            output_text += f"\n{current_speaker}: "

        if item["type"] == "punctuation":
            output_text = output_text.rstrip()

        output_text += f"{content} "

    return output_text


async def transcribe_audio(
    model_id,
    bucket_name,
    file_name,
    file_content,
    output_bucket,
):

    # Upload Audio to s3 bucket
    s3_client = boto3.client(
        "s3",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )
    await upload_file_to_s3(
        file_obj=file_content,
        file_name=file_name,
        s3_client=s3_client,
        bucket_name=bucket_name,
    )

    transcribe_client = boto3.client(
        "transcribe",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )

    job_name = f"transcription-job-{uuid.uuid4()}"

    transcribe_client.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={"MediaFileUri": f"s3://{bucket_name}/{file_name}"},
        MediaFormat="mp3",
        LanguageCode="en-US",
        OutputBucketName=output_bucket,
        Settings={"ShowSpeakerLabels": True, "MaxSpeakerLabels": 2},
    )

    while True:
        job_status = transcribe_client.get_transcription_job(
            TranscriptionJobName=job_name,
        )

        status = job_status["TranscriptionJob"]["TranscriptionJobStatus"]
        if status in ["COMPLETED", "FAILED"]:
            break
        time.sleep(2)

    if status == "FAILED":
        raise HTTPException(status_code=400, detail="Transcription Job failed")

    transcript_key = f"{job_name}.json"
    transcript_obj = s3_client.get_object(
        Bucket=output_bucket,
        Key=transcript_key,
    )
    transcript_text = transcript_obj["Body"].read().decode("utf-8")
    transcript_json = json.loads(transcript_text)

    output_text = process_transcription(transcript_json)

    result = await summarize_transcription(
        model_id,
        transcript=output_text,
    )

    return result


@app.post("/summary")
async def audio_summary(
    model_id: str = "amazon.titan-text-lite-v1",
    file: UploadFile = File(...),
):
    """An endpoint for generating meeting summary from audio file"""
    # But first, ensure the cursor is at position 0:
    file.file.seek(0)

    response = await transcribe_audio(
        model_id=model_id,
        bucket_name=BUCKET_NAME,
        file_name=file.filename,
        file_content=file.file,
        output_bucket=OUTPUT_BUCKET_NAME,
    )

    return {"response": response}
