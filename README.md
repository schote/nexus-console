# Spectrum-Pulseq MRI Console

## Installation

It is recommended to install the package within a virtual environment. There are many options to create and manage virtual environments. Examples are [virtualenv](https://mothergeo-py.readthedocs.io/en/latest/development/how-to/venv-win.html), [venv](https://docs.python.org/3/library/venv.html), [conda](https://docs.conda.io/projects/conda/en/stable/) or [miniconda](https://docs.conda.io/en/latest/miniconda.html).
Here we briefly show, how to setup a virtual environment with miniconda. To get started, please ensure that a version of [miniconda](https://docs.conda.io/en/latest/miniconda.html) is installed at your system. You can verify the installation by running `conda --version`. Futher documentation on how to install and use miniconda can be found [here](https://conda.io/projects/conda/en/stable/user-guide/install/index.html).

You can check your python version by running `python --version`.

1. Open a new terminal/command prompt and go to the repository folder `/spectrum-pulseq`. For simplicity we are going to create our virtual environment in here, alternatively you can also create it in your default environments folder (configurable in the `.condarc`file which can be found in `C:\Users\<username>`) by using a different prefix. We create the environment with python version [3.10](https://peps.python.org/pep-0619/).
```
conda create --prefix=./.venv python==3.10
```

2. We activate the virtual environment with the following command.
```
conda activate .\.venv
```
Now, the path to your virtual environment should appear in front of the current path in your terminal/command prompt.

3. You can check your python version by running `python --version`, it should print some version of `3.10.XX`.

4. Within the activated virtual environment you can you `pip` to install [packages](https://pypi.org/). Anything you install within the virtual environment is only available if the environment is active. 

5. To install the console application just ensure that you are still in the repository directory and simply enter:
```
pip install -e .
```
If the installation was successful you are good to go.



### Troubleshooting

<details>
<summary>Miniconda was installed but the command `conda` cannot be found.</summary>
Ensure that you added conda to your system path. You may also want to restart your terminal/command prompt.
</details>

<details>
<summary>Timeout during creation of conda environment or package installation.</summary>
If you are at PTB, ensure that your proxy is configured correctly to install packages with pip or conda respectively.
</details>

---

## Repository Structure

...