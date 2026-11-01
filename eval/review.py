"""Print the source passages behind the disputed benchmark cases so you can check the answer key by eye."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from trustlayer.retrieval import get_collection
col = get_collection()
def show(title, ids=None, source=None, word=None):
    print("\n" + "=" * 72 + "\n" + title)
    r = col.get(ids=ids) if ids else col.get(where={"source": source})
    for i, d in zip(r["ids"], r["documents"]):
        if word is None or word in d.lower():
            print(f"--- {i}\n{d[:900]}")
show("Case 51 (account closure fee): chunk S163", ids=["S163"])
show("Case 54 (free NEFT): chunk S100", ids=["S100"])
show("Case 91 (loan processing fee): circular chunk S141", ids=["S141"])
show("Case 91: original loan document, processing fee", source="personal_loan.md", word="processing fee")
show("Case 99 (no-claim bonus): chunks S63 and S68", ids=["S63", "S68"])
show("Case 99: original health document, no-claim bonus", source="health_insurance.md", word="no-claim")
