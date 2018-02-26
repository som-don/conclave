#!/bin/bash
PARTY_ID=$1
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
for size in 10 100 1000 2000 3000;
do
   bash run.sh ${PARTY_ID} hybrid_join_data/${size};
done