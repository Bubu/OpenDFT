# OpenDFT

OpenDFT is a free and open source software that brings cutting edge solid state research to the people.
It is a graphical program that interacts with various scientific terminal based solid state software packages.
It visualizes inputs, such as the crystal structure and outputs, such as band structures and optical spectra and can start and control calculations, which are done by the
respective scientific solid state package.
OpenDFT is designed to be DFT engine agnostic so that you can easily switch between different scientific codes and compare results seamlessly. At the moment it supports
* exciting
* nwchem
* QuantumEspresso
* abinit

We are working on supporting more open source packages such as for example siesta.

### Installing

OpenDFT runs on windows and linux and python versions 2 and 3. In order to be able to run it you need to install its dependencies.

#### Ubuntu, Linux Mint, etc. (linux distros with aptitude package manager):

##### User install

First install the vtk library for python with:

sudo apt-get install python-vtk

Then download the packaged OpenDFT program from the [release](https://github.com/JannickWeisshaupt/OpenDFT/releases) page
Unzip the file and execute the OpenDFT executable in the folder from a terminal: <br>
cd OpenDFT<br>
./OpenDFT

##### Developer install

One of the dependencies (mayavi) is not easy to install for python3 on linux . Therefore we
recommend to use python2. Here is a step-by-step instruction how to install OpenDFT:

sudo apt-get update<br>
sudo apt-get install python-numpy python-pip python-scipy python-matplotlib<br>
sudo apt-get install python-dev -y <br>
sudo apt-get install python-qt4 <br>
sudo apt-get install python-vtk python-setuptools python-configobj <br>
sudo pip install mayavi (or "pip install --user mayavi". 
Then always do this for the following commmand) <br>

sudo apt-get install python-pyside <br>
sudo pip install six <br>
sudo pip install periodictable <br>
sudo pip install pymatgen (This is optional and will add optional functionality)<br>
sudo apt-get install git <br>

cd folder/where/you/want/to/install/ <br>
git clone https://github.com/JannickWeisshaupt/OpenDFT.git <br>
cd OpenDFT <br>
./main.py <br>

Add following command to your ~/.bashrc in order to be able to open 
OpenDFT everywhere from the terminal

alias OpenDFT=/directory/where/you/where/you/want/to/install/OpenDFT/main.py <br>

Now you can start OpenDFT with the command "OpenDFT" in the terminal.

For the full functionality of OpenDFT you also need to install scientific solid state packages
that will perform the calculations.

##### Nwchem
sudo apt-get install nwchem

##### Quantum espresso
sudo apt-get install quantum-espresso

##### Exciting
Download the latest release [here](http://exciting-code.org/carbon) and follow the instructions [here](http://exciting-code.org/carbon-download-and-compile-exciting) 
and [here](http://exciting-code.org/carbon-tutorial-scripts-and-environment-variables).

##### Updating
To update cd into the OpenDFT folder and then perform <br>
git pull

#### Windows

It is pretty difficult to install the solid state software packages on windows. It may be possible
with [mingw](http://www.mingw.org/). OpenDFT however runs on windows. You just need to install python3
and the dependencies. For installing the dependencies we recommend Christoph Gohlke's awesome
[repository](https://www.lfd.uci.edu/~gohlke/pythonlibs/) of precompiled windows binaries. 
The dependencies, which can be installed from Gohlke's repository are:
+ pyqt4
+ numpy
+ scipy
+ matplotlib
+ vtk
+ mayavi

Just download the right file from the repository and install it via pip with for example:

cd directory/where/I/downloaded/the/file <br>
pip install PyQt4‑4.11.4‑cp36‑cp36m‑win_amd64.whl

This would be the right file for python3.6 and the 64 bit version of python as indicated by
cp36m_amd64

Finally install git from [here](https://git-scm.com/) and do:

cd folder/where/you/want/to/install/opendft <br>
git clone https://github.com/JannickWeisshaupt/OpenDFT.git <br>
cd OpenDFT <br>
python main.py <br>

## Getting Started

### Example 1: Diamond band structure with quantum espresso