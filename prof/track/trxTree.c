/*
    Build en report allocations in form of indented hiearchy of calls that match
    each unique call stack.
    
    We use a ordering vector which contain the entry indexes and put that vector
    through qsort() to order the indexes.
    ffffffff
*/
#include <stdlib.h>
#include "trx.h"

extern int summary;

static char __inline__ typeChar(resType_t type)
{
    switch(type) {
    
        case RESTYPE_MEMORY: return 'm';
        case RESTYPE_FILE: return 'f';
        default: return '?';
    }
}

static void diveAndPrint(int cliIdx, int idx, int indent, int maxEntry, void **vector, size_t *total)
{
    int i, size;
    uint32_t *t1=vector[idx];
    if(!t1[indent+2]) return;
    size=t1[0];
    /* count all entries that match at that level and increment total size */
    for(i=idx+1; i<maxEntry; i++) {
    
        uint32_t *t2=vector[i];
        if(t2[indent+2]!=t1[indent+2]) break;
        size += t2[0];
    }
    /* tally */
    if(!indent) *total+=size;
    /* print that entry */
    if(!summary && size > 0) 
        cliPrt(cliIdx, "%*s0x%08x [%d] %c\n", indent*4, "", t1[indent+2], size, indent? ' ':typeChar(t1[1]));
    
    /* go to the next level or indent */
    if(indent<MAXCALLERS-1) diveAndPrint(cliIdx, idx, indent+1, i, vector, 0);
    
    /* check out the rest of the entries at the same level */
    if(i<maxEntry) {
    
        diveAndPrint(cliIdx, i, indent,  maxEntry, vector, total);
    }
}

void buildShowTree(int cliIdx, int nentries, void **vector, size_t *total)
{
    *total=0;
    diveAndPrint(cliIdx, 0, 0, nentries, vector, total);
}
