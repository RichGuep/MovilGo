import pandas as pd
import io
from services.github_service import get_repo

def load_excel(file):
    repo = get_repo()
    if not repo:
        return pd.DataFrame()

    contents = repo.get_contents(file)
    return pd.read_excel(io.BytesIO(contents.decoded_content))
