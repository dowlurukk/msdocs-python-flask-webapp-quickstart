# Use the official lightweight Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first (for caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all other source code into the container
COPY . .

# Expose port 8080 (Cloud Run default)
EXPOSE 8080

# Use gunicorn to run the Flask app
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
