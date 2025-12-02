FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir mysql-connector-python Faker

# Copy seed script
COPY seed.py .

CMD ["python", "seed.py"]
