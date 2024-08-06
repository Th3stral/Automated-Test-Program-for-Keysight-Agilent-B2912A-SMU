# Automated-Test-Program-for-Keysight-Agilent-B2912A-SMU
An automated test program for Keysight(Agilent) B2912A SMU created based on streamlit and ktb_2900 library

# Setting Up and Running the test program
This guide will walk you through the process of installing Python 3.10, navigating to your project directory, installing dependencies, and running a the test program.

## Prerequisites

- A computer running Windows, or Linux
- Internet connection

## Step 1: Install Python 3.10

1. **Download Python 3.10:**

   - Visit the official Python website: [https://www.python.org/downloads/](https://www.python.org/downloads/)
   - Choose the appropriate installer for your operating system (Windows, or Linux).
   - Click on the download link for Python 3.10.

2. **Install Python:**

   - **Windows:**
     - Run the downloaded `.exe` file.
     - Make sure to check the box that says "Add Python 3.10 to PATH" before clicking "Install Now."
   
   - **Linux:**
     - Open a terminal window.
     - Run the following commands:

     ```bash
     sudo apt update
     sudo apt install python3.10
     ```

3. **Verify Installation:**

   Open a terminal or command prompt and run:

   ```bash
   python3.10 --version
   ```

## Step 2: Navigate to Your Project Directory

Open Terminal or Command Prompt:.

Navigate to Your Project Directory:

```bash
cd path/to/your/project/directory
```

Replace `path/to/your/project/directory` with the actual path to your project.

## Step 3: Install Dependencies

Ensure `pip` is Installed:
If `pip` is not installed, you can install it by running:

```bash
python3.10 -m ensurepip --upgrade
```

Install Requirements:
Run the following command to install all necessary packages listed in `requirements.txt`:

```bash
pip install -r requirements.txt
```

## Step 4: Run the Streamlit App

Use the following command to run the test application:


```bash
streamlit run app.py
```

Access the App:
Once the server starts, open your web browser and go to the URL provided by Streamlit, typically:

```bash
http://localhost:8501
```
