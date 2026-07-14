# mailbot

## Setup

1. **Create and activate a virtual environment (optional but recommended):**
   
   **Mac/Linux:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
   **Windows:**
   ```cmd
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   Copy the example environment file and update it with your actual credentials.
   
   **Mac/Linux:**
   ```bash
   cp .env.example .env
   ```
   **Windows:**
   ```cmd
   copy .env.example .env
   ```

## Running the application

To run the main application:

**Mac/Linux:**
```bash
python3 main.py
```
**Windows:**
```cmd
python main.py
```
