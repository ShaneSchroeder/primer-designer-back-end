from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
import primer3

app = FastAPI()

origins = [
    "http://localhost:5173",  # For local development
    "http://frontend-service",  # Frontend service in Kubernetes
    "http://primered.shane-schroeder.com",  # If deployed externally
    "https://primered.shane-schroeder.com",  # If deployed externally
    "*",  # Allow all origins for now (can be restricted in production)
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PrimerDesignRequest(BaseModel):
    sequence: str
    primer_length: int
    gc_content: float

class PrimerDetail(BaseModel):
    sequence: str
    tm: float
    gc_percent: float
    penalty: float
    start: int
    length: int

class PrimerResponse(BaseModel):
    left_primer: PrimerDetail
    right_primer: PrimerDetail
    internal_primers: List[PrimerDetail]

@app.get("/")
async def root():
    return {"Hello": "World"}


@app.post("/design-primer/")
async def design_primer(request: PrimerDesignRequest) -> PrimerResponse:
    sequence = request.sequence
    primer_length = request.primer_length
    gc_content = request.gc_content

    # Dynamically set product size range based on sequence length
    sequence_length = len(sequence)
    
    # Ensure product size range fits within sequence length
    min_product_size = max(primer_length * 2, 50)  # Minimum product size, at least double the primer length
    max_product_size = sequence_length  # Maximum product size is the entire sequence length

    if min_product_size > max_product_size:
        raise ValueError(f"The sequence length {sequence_length} is too short for the requested primer length {primer_length}.")

    # Define the product size range (min size, max size)
    product_size_range = [(min_product_size, max_product_size)]

    # Configure the Primer3 input parameters
    primer_design_input = {
        'SEQUENCE_TEMPLATE': sequence,
        'SEQUENCE_INCLUDED_REGION': (0, sequence_length),
        'PRIMER_OPT_GC_PERCENT': gc_content,
        'PRIMER_OPT_SIZE': primer_length,
        'PRIMER_MIN_SIZE': primer_length - 2,
        'PRIMER_MAX_SIZE': primer_length + 2,
        'PRIMER_PRODUCT_SIZE_RANGE': product_size_range,  # Add product size range
        'PRIMER_NUM_RETURN': 1  # Return one pair of primers
    }

    # Design primers using Primer3
    primer_results = primer3.bindings.designPrimers(
        primer_design_input,
        {
            'PRIMER_OPT_SIZE': primer_length,
            'PRIMER_MIN_SIZE': primer_length,
            'PRIMER_MAX_SIZE': primer_length,
            'PRIMER_OPT_GC_PERCENT': gc_content,
            'PRIMER_PRODUCT_SIZE_RANGE': product_size_range,  # Correct the argument
            'PRIMER_NUM_RETURN': 1  # Return a single primer pair
        }
    )

    # Extract primer details (as in your original code)
    left_primer = primer_results['PRIMER_LEFT_0_SEQUENCE']
    right_primer = primer_results['PRIMER_RIGHT_0_SEQUENCE']
    left_primer_tm = primer_results['PRIMER_LEFT_0_TM']
    right_primer_tm = primer_results['PRIMER_RIGHT_0_TM']
    left_primer_gc = primer_results['PRIMER_LEFT_0_GC_PERCENT']
    right_primer_gc = primer_results['PRIMER_RIGHT_0_GC_PERCENT']
    left_primer_penalty = primer_results['PRIMER_LEFT_0_PENALTY']
    right_primer_penalty = primer_results['PRIMER_RIGHT_0_PENALTY']

    # Internal primers can also be extracted if available
    internal_primers = []
    for i in range(primer_results['PRIMER_INTERNAL_NUM_RETURNED']):
        internal_primers.append(
            PrimerDetail(
                sequence=primer_results[f'PRIMER_INTERNAL_{i}_SEQUENCE'],
                tm=primer_results[f'PRIMER_INTERNAL_{i}_TM'],
                gc_percent=primer_results[f'PRIMER_INTERNAL_{i}_GC_PERCENT'],
                penalty=primer_results[f'PRIMER_INTERNAL_{i}_PENALTY'],
                start=primer_results[f'PRIMER_INTERNAL_{i}'][0],
                length=primer_results[f'PRIMER_INTERNAL_{i}'][1]
            )
        )

    return PrimerResponse(
        left_primer=PrimerDetail(
            sequence=left_primer,
            tm=left_primer_tm,
            gc_percent=left_primer_gc,
            penalty=left_primer_penalty,
            start=primer_results['PRIMER_LEFT_0'][0],
            length=primer_results['PRIMER_LEFT_0'][1]
        ),
        right_primer=PrimerDetail(
            sequence=right_primer,
            tm=right_primer_tm,
            gc_percent=right_primer_gc,
            penalty=right_primer_penalty,
            start=primer_results['PRIMER_RIGHT_0'][0],
            length=primer_results['PRIMER_RIGHT_0'][1]
        ),
        internal_primers=internal_primers
    )