# Meeting Transcription and Summarization API

## Overview
This FastAPI project provides an API for transcribing meeting audio recordings and generating a concise summary using AWS services. Users upload an audio file, and the API:
1. Transcribes the audio file using **AWS Transcribe**.
2. Processes the transcription into a prompt template.
3. Generates a summary using **AWS Bedrock's base model** as per the provided instructions in the prompt.

## Features
- **Audio File Upload**: Upload audio recordings in `.mp3` format.
- **Automatic Transcription**: Uses AWS Transcribe to convert audio into text, including speaker labeling.
- **Meeting Summarization**: Summarizes the transcribed text into key points, sentiment analysis, and identified issues.
- **Customizable Prompt**: The summarization prompt is based on a configurable Jinja2 template.
- **JSON Output**: Returns structured output in JSON format, including the meeting topic, summary, sentiment, and identified issues.

## API Endpoints

### `POST /summary`
Generate a meeting summary from an uploaded audio file.

#### Request
- **Parameters**:
  - `model_id` (str, optional): The ID of the AWS Bedrock model to use for summarization. Defaults to `amazon.titan-text-lite-v1`.
- **Body**:
  - `file`: Audio file to be uploaded. Must be in `.mp3` format.

#### Example cURL Request
```bash
curl -X POST "http://127.0.0.1:8000/summary" \
-H "Content-Type: multipart/form-data" \
-F "file=@meeting_audio.mp3" \
-F "model_id=amazon.titan-text-lite-v1"
```

#### Response
- **Success (200)**:
  ```json
  {
      "response": {
          "topic": "Project Updates",
          "meeting_summary": "The meeting discussed progress on the Q1 deliverables...",
          "sentiment": "positive",
          "issues": [
              {
                  "topic": "Timeline Delay",
                  "summary": "The team noted delays in the design phase."
              }
          ]
      }
  }
  ```
- **Failure (400/500)**:
  ```json
  {
      "detail": "Error message describing the issue."
  }
  ```

## Configuration
The project uses environment variables for sensitive configuration:
- `AWS_REGION`: AWS region for accessing services.
- `AWS_ACCESS_KEY_ID`: AWS access key ID.
- `AWS_SECRET_ACCESS_KEY`: AWS secret access key.
- `AWS_BUCKET_NAME`: Name of the S3 bucket for audio uploads.
- `OUTPUT_BUCKET_NAME`: Name of the S3 bucket for transcription output.

### Environment Configuration
Create a `.env` file with the following keys:
```env
AWS_REGION=your_aws_region
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_BUCKET_NAME=your_bucket_name
OUTPUT_BUCKET_NAME=your_output_bucket_name
```

## Prompt Template
The summarization process uses a Jinja2 template for generating prompts:
```jinja2
I need to analyze and summarize a conversation. The transcript of the
conversation is between the <data> XML-like tags.

<data>
{{transcript}}
</data>

Please do the following:

1. Identify the main topic being discussed in the conversation.
2. Provide a concise summary of the meeting, highlighting the key points.
3. Include a one-word sentiment analysis.
4. List any issues, problems, or causes of friction that arose during the conversation.

Format the output in JSON as shown in the example below. Write only the JSON output and nothing more.

Example output:
{
    "topic": "<main_topic>",
    "meeting_summary": "<concise_summary_highlighting_main_points>",
    "sentiment": "<one_word_sentiment>",
    "issues": [
        {
            "topic": "<short_issue_topic>",
            "summary": "<description_of_the_issue>"
        }
    ]
}

Here is the JSON output:
```

## Dependencies
- **Python 3.12+**
- **Poetry 1.8+**
- FastAPI
- Boto3
- Decouple
- Jinja2

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/bokal2/meeting-summarizer-backend.git
   cd meeting-summarizer-backend
   ```
2. Start a new poetry environment:
   ```bash
   poetry shell
   ```
3. Install dependencies:
   ```bash
   poetry install
   ```
4. Set up your environment variables in a `.env` file.

### Run the Application
Start the FastAPI server locally:
```bash
uvicorn main:app --reload
```

## Architecture
1. **Audio Upload**: The audio file is uploaded to an S3 bucket.
2. **AWS Transcribe**: Converts the audio into text and saves the transcription to another S3 bucket.
3. **Prompt Generation**: Uses a Jinja2 template to create a summarization prompt.
4. **AWS Bedrock**: Sends the prompt to AWS Bedrock, which generates the meeting summary.
5. **JSON Response**: Returns the structured summary as JSON.

## License
This project is licensed under the MIT License. See the `LICENSE` file for details.
