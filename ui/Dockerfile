FROM python:3.12

WORKDIR /

COPY ./requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r ./requirements.txt

COPY ./src .

ENTRYPOINT ["python3","./client.py"]