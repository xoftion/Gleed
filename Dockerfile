# Use the official Python 3.12 slim image as a base
FROM python:3.12-slim

# Set environment variables to prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE 1
# Set environment variables to ensure that output is sent straight to the terminal without being buffered
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Update the package manager and install system dependencies
# ffmpeg is required by yt-dlp for video processing
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    # Clean up apt-get lists to reduce image size
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Make the build and start scripts executable
RUN chmod +x ./build.sh ./start.sh

# Run the build script to perform setup tasks
# This will be executed when the Docker image is built
RUN ./build.sh

# Expose the port the app runs on. Render will set the PORT variable.
# We default to 8080 in the start.sh script if it's not set.
EXPOSE 8080

# The command to run when the container starts
CMD ["./start.sh"]