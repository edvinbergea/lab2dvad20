import itertools
import numpy as np
lista = [1,2,3,4,5,6]

#print(list(zip(lista[::2], lista[1::2])))
lista = list(zip(lista[::2], lista[1::2]))
#lista = list(zip(lista, lista))
listd = [lista[i] for i in range(len(lista)) for _ in range(2)]
print(listd)
listb = [1,2,3]
listc = [5,6,7,8,9]
cykel = itertools.cycle(listb)
