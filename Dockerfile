FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y build-essential

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --upgrade aioboto3 aiobotocore boto3

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000" ]

