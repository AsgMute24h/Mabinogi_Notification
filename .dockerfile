FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ENV TZ=Asia/Seoul
CMD ["python", "bot.py"]
