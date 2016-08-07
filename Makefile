IMAGE_NAME ?= docker-make

image:
	docker build -t $(IMAGE_NAME) . 
