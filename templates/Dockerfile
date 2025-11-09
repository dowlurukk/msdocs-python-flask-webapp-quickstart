# Use the official Python image from Docker Hub
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy all project files into the container
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 8080 (Cloud Run requires this)
EXPOSE 8080

# Run your Flask app with gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
