IMAGE="${IMAGE:-docker-make}"
alias docker-make="docker run -v \$(pwd):/data -v /var/run/docker.sock:/var/run/docker.sock $IMAGE"
