# Use an official Python runtime as a parent image
FROM python:3.11-slim-bullseye

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive \
    PATH="/usr/local/bin:$PATH"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    unzip \
    curl \
    bash \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libc6 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libexpat1 \
    libgbm1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxshmfence1 \
    libxtst6 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists

# Install Google Chrome

RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*


 # Install ChromeDriver
RUN set -eux; \
    CHROME_VERSION=$(google-chrome --version | grep -oE '[0-9]+(\.[0-9]+){3}' | cut -d '.' -f 1); \
    echo "Detected Chrome major version: $CHROME_VERSION"; \
    DRIVER_VERSION=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_VERSION}"); \
    echo "Matching ChromeDriver version: $DRIVER_VERSION"; \
    wget -q "https://storage.googleapis.com/chrome-for-testing-public/${DRIVER_VERSION}/linux64/chromedriver-linux64.zip" -P /tmp; \
    unzip -q /tmp/chromedriver-linux64.zip -d /usr/local/bin/; \
    ln -sf /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver; \
    chmod +x /usr/local/bin/chromedriver; \
    rm -rf /tmp/chromedriver-linux64.zip
 
 # Set the working directory in the container
 WORKDIR /app
 
 # Copy the requirements file into the container
 COPY requirements.txt .
 
 # Install Python dependencies
 RUN pip install --no-cache-dir -r requirements.txt \
     && pip install --no-cache-dir selenium webdriver-manager undetected-chromedriver
 
 
 # Copy the rest of the application code
 COPY . .
 
 # Ensure ChromeDriver has correct permissions
 RUN chmod +x /usr/local/bin/chromedriver || true
 
 # Expose the port the app runs on
 EXPOSE 8080



