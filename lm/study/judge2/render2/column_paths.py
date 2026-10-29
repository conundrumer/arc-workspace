"""Identity and presentation of native typed column paths."""
import json
from native import require


def key(path):
    require(isinstance(path,list),'native column path is not a list')
    result=[]
    for part in path:
        require(isinstance(part,dict),'native column path segment is not an object')
        kind=part.get('kind')
        if kind=='written':
            value=part.get('name');require(isinstance(value,str),'native written column name missing')
        else:
            require(kind=='slot','unknown native column path kind')
            value=part.get('slot');require(type(value) is int and value>=0,'native column slot missing')
        result.append((kind,value))
    return tuple(result)


def text(path,policy='held'):
    parts=key(path)
    require(policy in ('held','role'),'unknown column path display policy')
    if policy=='held':
        return '.'.join(value if kind=='written' else 'column '+str(value+1) for kind,value in parts)
    rendered=''
    for kind,value in parts:
        if kind=='slot':rendered+='['+str(value+1)+']'
        else:
            name=value if value.isidentifier() else json.dumps(value,ensure_ascii=False)
            rendered+=('.' if rendered else '')+name
    return rendered or 'Value'
