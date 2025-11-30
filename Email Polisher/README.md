# AI Email Tone Polisher

## Quick start
1. Create a virtual environment and install dependencies:
pip install -r requirements.txt

2. If you plan to use Gmail API:
- Create an OAuth client in Google Cloud Console (Application type: Desktop app).
- Download the JSON and save it as `credentials.json` in the project root.
- Run:
  ```
  python authorize.py
  ```
  Follow the browser consent flow. `token.json` will be created.

3. Run the app:
streamlit run app.py


## SMTP fallback
- Enable the sidebar checkbox "Enable SMTP fallback".
- Provide your Gmail address and an App Password (requires 2-Step Verification).
- The app will use SMTP when the checkbox is enabled.

## Testing polishing
- Run:
python test_polish.py

to see sample inputs and polished outputs.

## Notes and troubleshooting
- If `token.json` is missing, the app will show an error and SMTP fallback is available.
- Do not commit `credentials.json` or `token.json` to a public repo.
- Use the "Show debug info" checkbox in the sidebar to inspect `last_polished` and analytics during development.

## Files included
- `app.py` main Streamlit app
- `authorize.py` helper to create `token.json`
- `requirements.txt` pinned dependencies
- `test_polish.py` polishing tests
- `README.md` this file

