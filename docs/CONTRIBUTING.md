# Contributing to Viseron
Everyone is welcome to contribute to Viseron.\
I will gladly accept any pull request that is opened, as long as it follows the [style guidelines](#style-guidelines) outlined below.

If you want to contribute but you dont know how to code, please use the links below to sponsor Viseron or make a donation.

<a href="https://github.com/sponsors/roflcoopter" target="_blank"><img src="img/sponsor_button.png" alt="Sponsor" style="height: 37px !important;width: 170px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5)" ></a>
<a href="https://www.buymeacoffee.com/roflcoopter" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me A Coffee" style="height: 41px !important;width: 174px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;" ></a>

---

## Setup your local environment
Some setup is required in order to do efficient development.
- Install the dependencies: `pip3 install -r requirements.txt -r requirements_test.txt`.\
  It might be wise to do this in a `virtualenv` but this is up to you.
- Install `docker`
- Install `docker-compose`
- Install `tox`

---

## Style guidelines
All code is linted with quite strict [PEP 8 (Style Guide for Python Code)](https://www.python.org/dev/peps/pep-0008/) and [PEP 257 (Docstring Conventions)](https://www.python.org/dev/peps/pep-0257/) coding conventions.

To accommodate this a few tools are used.

- [pylint](https://www.pylint.org/) to enforce the PEP's above
- [flake8](https://flake8.pycqa.org/en/latest/) to enforce the PEP's above
- [Black](https://black.readthedocs.io/en/stable/) is used for code formatting
- [isort](https://pycqa.github.io/isort/) for sorted imports
- [codespell](https://github.com/codespell-project/codespell) to catch common misspellings
- [pytest](https://docs.pytest.org/en/6.2.x/) for testing

I suggest that you setup your IDE to match these requirements which makes development faster and easier.

---

## Development guidelines
The development process with `tox` is quite new for me so if you run into any issues, please let me know and we can work it out.

- Fork the Viseron repo
- Write your code
- Create tests for your new code
- Run `tox` to test and lint your code (**make sure all checks pass or your PR will be rejected**)
- Create a PR towards the `dev` branch

### Using tox
`tox` is the main tool used for linting and testing your code.\
Simply running the command `tox` will run all checks. You can single out a specific check by supplying the `-e` flag.\
For example:
- Run pylint only: `tox -e pylint`
- Run pytest only: `tox -e pytest`

#### A note on pytest
Viseron requires a lot of dependencies.\
To make testing with `pytest` as easy as possible, `tox` will build and run a Docker container which executes `pytest`.\
If you would like to run tests outside of `tox` you can build and run this container manually:
```
docker-compose --file azure-pipelines/docker-compose-build.yaml --env-file azure-pipelines/.env build amd64-viseron-tests
docker-compose --file azure-pipelines/docker-compose-build.yaml --env-file azure-pipelines/.env run --rm amd64-viseron-tests
```

### Develop Docker containers
Viseron heavily uses multistage Docker builds, and compilation of different components are split into different Dockerfiles.
To build all the `amd64` image from scratch the following commands can be used.
```bash
docker-compose --file ./azure-pipelines/docker-compose-build.yaml --env ./azure-pipelines/.env build amd64-ffmpeg && \
docker-compose --file ./azure-pipelines/docker-compose-build.yaml --env ./azure-pipelines/.env build amd64-opencv && \
docker-compose --file ./azure-pipelines/docker-compose-build.yaml --env ./azure-pipelines/.env build amd64-dlib && \
docker-compose --file ./azure-pipelines/docker-compose-build.yaml --env ./azure-pipelines/.env build amd64-wheels && \
docker-compose --file ./azure-pipelines/docker-compose-build.yaml --env ./azure-pipelines/.env build amd64-base && \
docker-compose --file ./azure-pipelines/docker-compose-build.yaml --env ./azure-pipelines/.env build amd64-viseron
```

Lets say you want to update to a newer version of OpenCV.\
To do this you would:
- Edit `OPENCV_VERSION` in ./azure-pipelines/.env
- Build the OpenCV image: `docker-compose --file ./azure-pipelines/docker-compose-build.yaml --env ./azure-pipelines/.env build amd64-opencv`
- Build Viseron image: `docker-compose --file ./azure-pipelines/docker-compose-build.yaml --env ./azure-pipelines/.env build amd64-viseron`

#### Cross-building
To support different CPU architectures i use [Balenas base images](https://www.balena.io/docs/reference/base-images/base-images/) that runs QEMU.\
To build these you need to first register QEMU on your builder.

The easiest way to do that is to run `docker run --rm --privileged tonistiigi/binfmt --install all`\
You can then simply build the containers like you normally would and QEMU will be invoked automatically.
