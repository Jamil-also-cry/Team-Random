import fitz, sys, io
doc = fitz.open(r"c:\Users\Sabab\Downloads\kenney_platformer-art-extended-tileset\BUP_CSE_FEST_2026_Participant_Docs\BUP_CSE_FEST_2026_Preliminary_Problem_Statement_GridWise_LLM.pdf")
out = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
print("pages:", len(doc), file=out)
for i in range(len(doc)):
    print(f"\n===PAGE {i+1}===", file=out)
    print(doc[i].get_text(), file=out)
out.flush()
