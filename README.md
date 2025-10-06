# AI-Testing-Platform

This repository contains the initial source code and relevant files for my master thesis' project "Vulnerability testing sandbox environment for AI-systems"

**Optional gVisor setup**

https://gvisor.dev/docs/user_guide/install/

1.
```
(
  set -e
  ARCH=$(uname -m)
  URL=https://storage.googleapis.com/gvisor/releases/release/latest/${ARCH}
  wget ${URL}/runsc ${URL}/runsc.sha512 \
    ${URL}/containerd-shim-runsc-v1 ${URL}/containerd-shim-runsc-v1.sha512
  sha512sum -c runsc.sha512 \
    -c containerd-shim-runsc-v1.sha512
  rm -f *.sha512
  chmod a+rx runsc containerd-shim-runsc-v1
  sudo mv runsc containerd-shim-runsc-v1 /usr/local/bin
)
```
2.
```
$ /usr/local/bin/runsc install
$ sudo systemctl reload docker
```

/etc/docker/daemon.json should look like this with nvidia and runsc runtimes installed:
```
{
    "runtimes": {
        "nvidia": {
            "path": "/usr/bin/nvidia-container-runtime",
            "runtimeArgs": []
        },
        "runsc": {
            "path": "/usr/local/bin/runsc"
        }
    }
}
```

*Setuping the tool*

1.

```git clone git@github.com:Kemppis3/AI-Testing-Platform.git```

2.

Create a Python virtual environtment and activate it

```python -m venv (name_of_your_venv)```

```source ./(name_of_your_venv)/bin/activate```

3.

Navigate to the tool folder

```cd ../AI-Testing-Platform```

4.


Give executon permissions for run-sandbox.sh script

```sudo chmod +x run-sandbox.sh```

5.

Build the docker image

```docker build -t (name_of_your_image) .```

6.

Run the testing tool by executing run-sandbox.sh script

```./run-sandbox.sh```

**NOTE: If you are not running gVisor, remove the gVisor active check from run-sandbox.sh and the $RUNTIME_FLAG from docker run command**







