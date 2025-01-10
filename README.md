# Pigeon alert

The motivation for this project is my obsession with pigeons polluting my balcony. First step is to create an alert
when pigeons are occur. Second step nobody knows...

## Set up info and steps I followed to test and ran camera inference

Hardware:
- Raspberry pi 5 8GB
- M.2 HAT+ with Hailo-8L chip (13 TOPS)
- Waveshare RPi camera (H)

1. Next, I installed AI chip using [presented manual](https://www.raspberrypi.com/documentation/accessories/ai-kit.html#install) and [hardware setup](https://www.raspberrypi.com/documentation/computers/ai.html#hardware-setup). To understand workflow I tried some demos they provide.
   Test if camera works (my camera is upside down, so I had to use rotation parameter):
    ```shell
    rpicam-hello --rotation 180 --timeout 0
    ```
2. Ran example from [hailo-rpi5-examples](https://github.com/hailo-ai/hailo-rpi5-examples)
3. I had to fix source script [using issue](https://github.com/hailo-ai/hailo-rpi5-examples/issues/48).
4. Presented code is fully based on hailo rpi5 detection example, where I am using only necessary code for detection.

note: for a development purpose i tried to install at least gobjects on mac, 
you have to install run `brew install pygobject3 gtk4`. Than run `make install-dev`

## Environment setup

Easy just run script (from rpi5 examples):
```shell
./install.sh
```
activate env and set all necessary variables:
```shell
source setup_env.sh
```

## Usage

```shell
source setup_env.sh
python src/detection.py -i rpi -t 10
```
I added `-t` flag for timer in seconds. 

## Cron job (Optional)

note: __not workin__
if you want to run job only at day-light set cron to (hourly)
```shell
0 * * * * cd /HailoProjects/pigeon-alert && ./cron.sh
```
default time out is 3590 seconds.

## Work log
- In examples of `hailo-rpi5-examples` I found and script for detection using wrapped yolo what includes a label "bird" lets use it for start!
- Rob the repository for minimum code I will need to ran and example.
- if detected label (bird for now) save frame, camera rotation done as postprocess
- add option to set the timer of the loop, handy for scheduling
- update tappas to 3.30.0
- add type annotation, it helped me gain intuition about how gstreamer works
- option to disable display, camera rotation

## Notes

- timelaps with [cron](https://www.raspberrypi.com/documentation/computers/camera_software.html#via-cron)
- [picamera](https://raspberrypifoundation.github.io/picamera-zero/)
- streaming on [youtube](https://projects.raspberrypi.org/en/projects/infrared-bird-box/9)

## TODO 
- pigeon sitting on balcony detected as person... find better model
- (maybe) connect to remote pycharm for faster development
- why display pipe is needed? HailoNet Error: gst_pad_push failed with status = -1
- fine tune hyper parameters, as Bx and limit for probability

## How to monitor your Hailo utilization

Start the Monitoring Tool:
In one terminal window, initiate the monitoring process:
```shell
hailortcli monitor
```

Run Your Inference Script:
In a separate terminal window, execute your Python inference script or any application utilizing the Hailo chip. 
Ensure that the HAILO_MONITOR environment variable is set in this terminal as well:
```shell
export HAILO_MONITOR=1
python <your_inference_script>.py
```
