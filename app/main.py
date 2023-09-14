import pickle
import io
import os
import json
import pandas as pd
import numpy as np
from langchain.embeddings import HuggingFaceEmbeddings
from sklearn.metrics.pairwise import cosine_similarity
from decimal import Decimal

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel


emb_path = "emb.bin"
purpose_vec_path = "purpose_vectors.npy"


if os.path.exists(emb_path):
    with open(emb_path, "rb") as f:
        embeddings = pickle.load(f)
else:
    embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-base")
    with open(emb_path, 'wb') as p:
        pickle.dump(embeddings, p)

purpose = pd.read_csv("purpose.csv", dtype ="str")
statcode = purpose["statcode"].values.tolist()

if os.path.exists(purpose_vec_path):
    vectors = np.load(purpose_vec_path)
else:
    vectors = [embeddings.embed_documents([p]) for p in purpose["purpose"].values.tolist()]
    np.save(purpose_vec_path, vectors)
    

app = FastAPI(
    title = "vector stat search",
    description = "調査の目的をベクトル化して統計調査を検索する試み",
    version = "0.0.1"
)


class searchResult(BaseModel):
    statcode: str
    purpose: str
    statname: str  

def vector_search_core(keyword: str, count: int, score: Decimal):

    q = embeddings.embed_documents([keyword])
    sims = [cosine_similarity(vec, q) for vec in vectors]
    hits  = np.argsort(sims, axis=None)[-count:]
    selection = [statcode[hit] for hit in  hits]
    sims_ = [sims[hit][0][0] for hit in hits]    
    
    scores = pd.DataFrame({"statcode": selection, "similarity": sims_})
    
    ret = pd.merge(
                purpose[purpose["statcode"].isin(selection)],
                scores,
                on = "statcode",
                how = "left"
            )

    if score != 0:
        ret = ret[ret["similarity"] >= score]    
    

    return(ret.sort_values('similarity',ascending=False).to_dict(orient='records'))

    

@app.get("/search.json", response_class=JSONResponse)
def read_search_json(keyword: str, count: int = 5, score: Decimal = 0):
    
    return(JSONResponse(content=vector_search_core(keyword, count, score)))


