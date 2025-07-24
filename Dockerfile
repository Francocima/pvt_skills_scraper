# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    bash \
    wget \
    gnupg \
    unzip \
    curl \
    # Install dependencies for Chrome
    libgconf-2-4 \
    # Install Chrome dependencies
    libx11-6 \
    libx11-xcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxi6 \
    libxtst6 \
    libnss3 \
    libcups2 \
    libxss1 \
    libxrandr2 \
    libgbm1 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libpango-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    ca-certificates \
    # Clean up
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome

RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*


 # Install ChromeDriver
 RUN wget https://storage.googleapis.com/chrome-for-testing-public/138.0.7204.92/linux64/chromedriver-linux64.zip -P /tmp \
     && unzip /tmp/chromedriver-linux64.zip -d /usr/local/bin/ \
     && rm /tmp/chromedriver-linux64.zip \
     && chmod +x /usr/local/bin/chromedriver-linux64/chromedriver \
     && ln -s /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \
     && chromedriver --version \
     && google-chrome --version
 
 # Set the working directory in the container
 WORKDIR /app
 
 # Copy the requirements file into the container
 COPY requirements.txt .
 
 # Install Python dependencies
 RUN pip install --no-cache-dir -r requirements.txt \
     && pip install selenium webdriver-manager undetected-chromedriver
 
 
 # Copy the rest of the application code
 COPY . .
 
 # Ensure ChromeDriver has correct permissions
 RUN chmod +x /root/.wdm/drivers/chromedriver/linux64/*/chromedriver-linux64/chromedriver || true
 
 # Expose the port the app runs on
 EXPOSE 8080



