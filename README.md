# Spectrum-Pulseq MRI Console

This project aims to implement a console for magnetic resonance imaging (MRI) acquisitions. The central hardware components are two spectrum cards from Spectrum Instrumentation. They serve as arbitrary waveform generators (AWG) and analog to digital converter (digitizer). This application controls AWG and digitizer cards to perform MRI scans from a sequence description with the open-source pulseq framework. The console application is formerly designed for low-field applications, but might be extendable also for higher field strength.

## Installation

It is recommended to install the package within a virtual environment. There are many options to create and manage virtual environments. Examples are [virtualenv](https://mothergeo-py.readthedocs.io/en/latest/development/how-to/venv-win.html), [venv](https://docs.python.org/3/library/venv.html), [conda](https://docs.conda.io/projects/conda/en/stable/) or [miniconda](https://docs.conda.io/en/latest/miniconda.html).
Here we briefly show, how to setup a virtual environment with miniconda. To get started, please ensure that a version of [miniconda](https://docs.conda.io/en/latest/miniconda.html) is installed at your system. You can verify the installation by running `conda --version`. Futher documentation on how to install and use miniconda can be found [here](https://conda.io/projects/conda/en/stable/user-guide/install/index.html).

You can check your python version by running `python --version`.

Install `spectrum-console`:

1. **Open a new terminal/command prompt to create a new virtual environment.**
   
   We are using conda, but of course you can use any other tool to create a virtual environment as well. We create the environment with python version [3.11](https://peps.python.org/pep-0664/).
   
   ```
   conda create <env-name> python==3.11
   ```

   _Hint: 
   We use the defalt environment directory, but you can also create it in custom environments folder (configurable in the `.condarc` file which should be located in your home directory). Use `--prefix <custom/destination/>` to choose an individual path for the conda enironment._

2. **Activate the virtual environment**
   ```
   conda activate <env-name>
   ```
   Now the name of the virtual environment should appear in front of the current path in your terminal/command prompt.
   
   _Hint: You can check your python version by running `python --version`, it should print some version of `3.10.XX`._

3. **Install the package**
   
   To install the console application, ensure that you are in the repository directory (`*/spectrum-console/`). The enter the following command.
    
    ```
    pip install -e .
    ```

    To install optional dependencies you can use one of the following commands or similar:
    ```
    pip install -e ".[lint]"
    pip install -e ".[test]"
    pip install -e ".[lint, test]"
    ```
    
    _Hint: Within the activated virtual environment you can install additional [packages](https://pypi.org/) with `pip`. Anything you install within the virtual environment is only available if the environment is active. Packages which should be installed with the project should be added to the `pyproject.toml` file_


## Troubleshooting

### Installation

<details>
<summary>Miniconda was installed but the command `conda` cannot be found.</summary>
Ensure that you added conda to your system path. You may also want to restart your terminal/command prompt.
</details>

<details>
<summary>Timeout during creation of conda environment or package installation.</summary>
If you are at PTB, ensure that your proxy is configured correctly to install packages with pip or conda respectively.
</details>

<details>
<summary>ValueError: Mime type rendering requires nbformat>=4.2.0 but it is not installed</summary>
If you are at PTB, ensure that your proxy is configured correctly to install packages with pip or conda respectively.
</details>


---

## Repository Structure

...
