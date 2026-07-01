FROM python:3.11
WORKDIR /app
COPY . /app
RUN pip install '.'
EXPOSE 8000
CMD ["nemi", "start","--port","8000","--host","0.0.0.0"]
