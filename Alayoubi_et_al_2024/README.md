## Create conda environment
```$ mamba create -n scanpro_analysis 'python>=3.9' anndata r-base=4.3 r-devtools r-seurat 'matplotlib<=3.8.4' ipykernel ipywidgets```
```$ conda activate scanpro_analysis ```

## Install scanpro
`$ pip install scanpro`

## Install sccoda
`$ pip install pertpy`

## Install propeller from the speckle package
`$ pip install rpy2`

In R, run:
```R
library(devtools)
devtools::install_github("phipsonlab/speckle")
```

## Register the kernel for jupyter notebooks
`$ python -m ipykernel install --user --name scanpro_analysis `