**Goa Police Hackathon 2025 – AI-Powered CCTV & Digital Media Forensic Analysis Tool**

💡 Proposed Solution

We propose an AI-driven forensic toolkit that integrates computer vision and digital integrity checks into a single solution.
Core Capabilities:

 1.⁠ ⁠CCTV Analysis
 2.⁠ ⁠Automatic detection and tracking of people and vehicles.
 3.⁠ ⁠Time-stamped appearance logs linked to unique IDs.
 4.⁠ ⁠Matching against offender databases with high accuracy.
 5.⁠ ⁠Forensic Media Analysis
 6.⁠ ⁠Extraction of metadata (timestamps, device info).
 7.⁠ ⁠File integrity verification through cryptographic hashing.
 8.⁠ ⁠Tamper detection with clear anomaly flags.
 9.⁠ ⁠Investigator Dashboard & Reporting
10.⁠ ⁠Searchable interface to review detections and evidence.
11.⁠ ⁠Tamper-proof forensic PDF reports containing hashes, logs, and detection videos.    
12.⁠ ⁠Built-in audit trail to preserve chain of custody.

Expected Outcomes:

•⁠  ⁠A reliable, investigator-friendly platform that:
•⁠  ⁠Saves investigation time by automating video review.
•⁠  ⁠Enhances the credibility of digital evidence with forensic validation.
•⁠  ⁠Provides police with actionable insights and tamper-proof reports.
•⁠  ⁠Strengthens citizen safety by enabling faster and more accurate investigations.


Setting up the Virtual Environment 

** FOR MAC **

1. Install pyenv
If you don’t already have pyenv, install it via Homebrew:
    brew update
    brew install pyenv

Add pyenv to your shell so it works properly:
If you use zsh (default on mac):
    echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
    echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
    echo 'eval "$(pyenv init --path)"' >> ~/.zshrc
    echo 'eval "$(pyenv init -)"' >> ~/.zshrc
    source ~/.zshrc

If you use bash:
    echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
    echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
    echo 'eval "$(pyenv init --path)"' >> ~/.bashrc
    echo 'eval "$(pyenv init -)"' >> ~/.bashrc
    source ~/.bashrc

2. Install Python 3.11.9
Now install the specific version of python
    pyenv install 3.11.9

If you get errors like zlib not found, install required build dependencies first:
    brew install openssl readline sqlite3 xz zlib tcl-tk


3. Create a project folder
Choose a directory for your project which is the extracted zip file Corinthian-main :
    cd Corinthian-main

4. Set Python version locally
Tell pyenv to use Python 3.11.9 inside this folder:
    pyenv local 3.11.9

Now check:
    python --version

It should show:
    Python 3.11.9


5. Create a virtual environment
With Python 3.11.9 active, create a venv:
    python -m venv venv

This will create a folder named venv inside your project.

6. Activate the virtual environment
Run:
    ```source venv/bin/activate```

You’ll see (venv) in your terminal prompt.
Check again:
```python --version```

It should still show 3.11.9

Upgrade pip before installing (important for newer packages):
    ```pip install --upgrade pip setuptools wheel```

Install from requirements.txt:
    ```pip install -r requirements.txt```

for safety, deactive venv by running: ```deactivate```
and restart the terminal
start the venv again by ```source venv/bin/activate```

🔹 Potential Issues to Watch Out For
Some of the packages in your list are heavy and sometimes tricky with Mac + Python 3.11:
dlib + face-recognition
 → These often fail unless you have CMake and Xcode Command Line Tools installed.
 Run this first if needed:
    brew install cmake
    xcode-select --install

tensorflow
 → On Mac, pip install tensorflow pulls a CPU-only build (Apple Silicon uses tensorflow-macos).
If you’re on Intel Mac, it should work. If on M1/M2, you may need to replace it with:
    pip install tensorflow-macos
torch / torchvision
 → pip install torch usually works, but sometimes you need to specify the version.
 Example for CPU:
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

If you are getting [SSL: CERTIFICATE_VERIFY_FAILED ERROR]:
Install pip-system-certs (Most Effective)
This is the most reliable solution for corporate/restrictive environments:
    pip install pip-system-certs


🔹 Verify installation
After installation finishes, test:
python -c "import torch, tensorflow, cv2, face_recognition; print('All good')"

If no errors → you’re set!

Initial runs will take time.

** Windows **
Open PowerShell as Administrator and run:
    winget install Python.Python.3.11

    Remove or Degrade Other Python Versions (If Necessary)
    If you already have a newer Python and wish to remove it:
    pen Settings → Apps → Installed apps.
    Find the undesired Python version(s) and click Uninstall.

    Alternatively, use winget:
    powershell
    winget uninstall --id=Python.Python.3.<version>
     3.⁠ ⁠Verify Python 3.11.9 Installation

In a new Command Prompt or PowerShell, run:
    py -3.11 --version

Expected output:
    Python 3.11.9

⁠Create a Virtual Environment with Python 3.11.9
    Choose a directory for your project which is the extracted zip file Corinthian-main :
        cd Corinthian-main

Using the py Launcher (Recommended)
Create a venv named venv
    py -3.11 -m venv venv

Activate it
    ```venv\scripts\activate```     # CMD


⁠Confirm Your Virtual Environment’s Python Version
With the venv activated, run:
    python --version

You should see:
    ```Python 3.11.9```

Inside your venv 
    pip install --upgrade pip setuptools wheel
    pip install -r requirements.txt

Initial runs will take time.

Criminal Database creation:
There is a sample Excel file in the db folder to create the database. The database(excel) should be in the db folder only.
ID: this should be the file name of the criminal’s photo
Name: Input the name of the criminal
Age: age of the criminal

Our code does the rest!!
