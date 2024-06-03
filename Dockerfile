FROM python:3

COPY requirements.txt /app/
COPY coopstorage /app/coopstorage
COPY api /app/api/
COPY main.py /app/

WORKDIR /app

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]