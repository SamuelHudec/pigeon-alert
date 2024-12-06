# Pigeon alert

The motivation for this project is my obsession with pigeons polluting my balcony. First step is to create an alert
when pigeons are occur. Second step nobody knows...

## Environment setup

Easy just run script:
```shell
./install.sh
```
activate env and set all necessary variables:
```shell
source setup_env.sh
```

## Set up info and steps I followed to test and ran camera inference

Hardware:
- Raspberry pi 5 8GB
- M.2 HAT+ with Hailo-8L chip (13 TOPS)
- Waveshare RPi camera (H)

Test if camera works:
```shell
rpicam-hello --rotation 180 --timeout 0
```
my camera is upside down, so I had to use rotation parameter.

Next, I installed AI chip using [presented manual](https://www.raspberrypi.com/documentation/accessories/ai-kit.html#install)
and [hardware setup](https://www.raspberrypi.com/documentation/computers/ai.html#hardware-setup). To understand workflow
I tried some demos they provide.

Ran example from [hailo-rpi5-examples](https://github.com/hailo-ai/hailo-rpi5-examples)
I had to fix source script [using issue](https://github.com/hailo-ai/hailo-rpi5-examples/issues/48).

for a development purpose i tried to install at least gobjects on mac, 
you have to install run `brew install pygobject3 gtk4`. Than run `make install-dev`

## Usage

```shell
source setup_env.sh
python src/detection.py -i rpi
```


## Work log
- In examples of `hailo-rpi5-examples` I found and script for detection using wrapped yolo what includes a label "bird" lets use it for start!
- Rob the repository for minimum code I will need to ran and example.
- if detected label (bird for now) save frame, camera rotation done as postprocess
- add option to set the timer of the loop, handy for next scheduling
- update tappas to 3.30.0

## Notes

- timelaps with [cron](https://www.raspberrypi.com/documentation/computers/camera_software.html#via-cron)
- [picamera](https://raspberrypifoundation.github.io/picamera-zero/)
- streaming on [youtube](https://projects.raspberrypi.org/en/projects/infrared-bird-box/9)

# TODO
- disable display
- polish scripts with respect of mypy of some other conventions
- (maybe) connect to remote pycharm for faster development

[pyenv]: https://github.com/pyenv/pyenv#installationbrew
[how to install pyenv on MacOS]: https://jordanthomasg.medium.com/python-development-on-macos-with-pyenv-2509c694a808
