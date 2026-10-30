"""Static data contracts. Runtime boundaries independently validate every field."""
from typing import Literal,TypedDict,Union
Label=Literal['1','W','A','S4','D','T6','P','Wp','V']
Classification=Literal['genuine','proper_virtual']
class Irrep(TypedDict):
    op:Literal['irrep']
    label:Label
class Virtual(TypedDict):
    op:Literal['virtual']
    coefficients:dict[Label,int]
class SymmetricPower(TypedDict):
    op:Literal['symmetric_power']
    degree:int
class Binary(TypedDict):
    op:Literal['add','subtract','tensor']
    left:'Expression'
    right:'Expression'
Expression=Union[Irrep,Virtual,SymmetricPower,Binary]
class Expectation(TypedDict):
    classification:Literal['any','genuine','proper_virtual']
    equals:dict[Label,int]|None
class RequestData(TypedDict):
    schema:Literal['fm-character-request-v1']
    expression:Expression
    expectation:Expectation
class ResultData(TypedDict):
    multiplicities:list[int]
    dimension:int
    classification:Classification
    center_parity:Literal['zero','even','odd','mixed']
    even_dimension:int
    odd_dimension:int
    negative_multiplicities:dict[Label,int]
class CertificateData(TypedDict):
    schema:Literal['fm-character-certificate-v1']
    catalog_sha256:str
    request_sha256:str
    request:RequestData
    result:ResultData
    class_values:list[list[int]]
    scope:Literal['universal_representation_arithmetic_only']
