FROM python:3.11
WORKDIR /app

# Install dependencies (cached forever unless requirements.txt changes)
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy full app code and install package (no re-download deps)
COPY . /app/
RUN pip install --no-cache-dir --no-deps '.'

EXPOSE 8000
CMD ["nemi", "start","--port","8000","--host","0.0.0.0"]
