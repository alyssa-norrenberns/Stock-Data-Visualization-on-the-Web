# use an official python image as the base image
FROM python:3.8-slim-buster

# set the working directory in the container to /app
WORKDIR /app

# copy the current directory contents into the container at /app
COPY . /app

# upgrade pip
RUN pip install --upgrade pip

# install required packages
RUN pip install --no-cache-dir -r requirements.txt

# set default commands to run when starting the container
CMD ["python", "app.py"]