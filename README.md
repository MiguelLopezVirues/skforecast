# skforecast

**Time series forecasting with scikit-learn regressors.**


## Installation

```bash
$ pip install git+https://github.com/JoaquinAmatRodrigo/skforecast@v0.1.4
```


## Dependencies

+ python>=3.7.1
+ numpy>=1.20.1
+ pandas>=1.2.2
+ tqdm>=4.57.0
+ scikit-learn>=0.24



## Features

+ Create autoregressive forecasters from any scikit-learn regressor.
+ Grid search to find optimal hyperparameters.
+ Grid search to find optimal lags (predictors).
+ Include exogenous variables as predictors.

## TODO

- [ ] Get predictor importance
- [ ] Parallel grid search
- [ ] Speed lag creation with numba
- [ ] Custom predictors
- [ ] Testing


## Introduction


A time series is a sequence of data arranged chronologically, in principle, equally spaced in time. Time series forecasting is the use of a model to predict future values based on previously observed values, with the option of also including other external variables.

When working with time series, it is seldom needed to predict only the next element in the series (*t+1*). Instead, the most common goal is to predict a whole future interval (*t+1, ..., t+n*)  or a far point in time (*t+n*).

Since the value of *t + 1* is required to predict the point *t + 2*, and *t + 1* is unknown, it is necessary to make recursive predictions in which, each new prediction , is based on the previous one. This process is known as recursive forecasting or multi-step forecasting and it is the main difference with respect to conventional regression problems.

<p><img src="./images/forecasting_multi-step.gif" alt="forecasting-python" title="forecasting-python"></p>

<br>

The main challenge when using scikit learn models for forecasting is transforming the time series in an matrix where, each value of the series, is related to the time window (lags) that precede it.

<p><img src="./images/transform_timeseries.gif" alt="forecasting-python" title="forecasting-python"></p>

<center><font size="2.5"> <i>Time series  transformation into a matrix of 5 lags and a vector with the value of the series that follows each row of the matrix.</i></font></center>

<br><br>

**Skforecast** is a python library that eases using scikit-learn regressors as multi-step forecasters.

## Examples

### Autoregressive forecaster

```python
# Libraries
# ==============================================================================
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.linear_model import Lasso
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error
```

```python
# Download data
# ==============================================================================
url = 'https://raw.githubusercontent.com/JoaquinAmatRodrigo/' \
      + 'Estadistica-machine-learning-python/master/data/h2o.csv'
datos = pd.read_csv(url, sep=',')

# Data preprocessing
# ==============================================================================
datos['fecha'] = pd.to_datetime(datos['fecha'], format='%Y/%m/%d')
datos = datos.set_index('fecha')
datos = datos.rename(columns={'x': 'y'})
datos = datos.asfreq('MS')
datos = datos['y']
datos = datos.sort_index()

# Split train-test
# ==============================================================================
steps = 36
datos_train = datos[:-steps]
datos_test  = datos[-steps:]


fig, ax=plt.subplots(figsize=(9, 4))
datos.plot(ax=ax, label='y')
ax.legend();
```

<p><img src="./images/data.png"</p>

```python
# Create and fit forecaster
# ==============================================================================
forecaster = ForecasterAutoreg(
                    regressor=LinearRegression(),
                    lags=15
                )

forecaster.fit(y=datos_train)
forecaster
```

```
=======================ForecasterAutoreg=======================
Regressor: LinearRegression()
Lags: [ 1  2  3  4  5  6  7  8  9 10 11 12 13 14 15]
Exogenous variable: False
Parameters: {'copy_X': True, 'fit_intercept': True, 'n_jobs': None, 'normalize': False, 'positive': False}
```

```python
# Predict
# ==============================================================================
steps = 36
predictions = forecaster.predict(steps=steps)
# Add datetime index to predictions
predictions = pd.Series(data=predictions, index=datos_test.index)

# Plot
# ==============================================================================
fig, ax=plt.subplots(figsize=(9, 4))
datos_train.plot(ax=ax, label='train')
datos_test.plot(ax=ax, label='test')
predictions.plot(ax=ax, label='predictions')
ax.legend();

# Prediction error
# ==============================================================================
error_mse = mean_squared_error(
                y_true = datos_test,
                y_pred = predictions
            )
print(f"Test error (mse): {error_mse}")
```

```
Test error (mse): 0.011051937043503587
```

<p><img src="./images/prediction.png"</p>

```python
# Grid search hiperparameters and lags
# ==============================================================================
forecaster = ForecasterAutoreg(
                regressor=RandomForestRegressor(random_state=123),
                lags=12
             )

# Regressor hiperparameters
param_grid = {'n_estimators': [50, 100],
              'max_depth': [5, 10]}

# Lags used as predictors
lags_grid = [3, 10, [1,2,3,20]]

results_grid = grid_search_forecaster(
                        forecaster  = forecaster,
                        y           = datos_train,
                        param_grid  = param_grid,
                        lags_grid   = lags_grid,
                        steps       = 10,
                        metric      = 'neg_mean_squared_error',
                        initial_train_size    = int(len(datos_train)*0.5),
                        allow_incomplete_fold = False,
                        return_best = True
                    )

# Results grid search
# ==============================================================================
results_grid
```

```
loop lags_grid:   0%|          | 0/3 [00:00<?, ?it/s]
loop param_grid:   0%|          | 0/4 [00:00<?, ?it/s]
loop param_grid:  25%|██▌       | 1/4 [00:00<00:02,  1.40it/s]
loop param_grid:  50%|█████     | 2/4 [00:02<00:02,  1.11s/it]
loop param_grid:  75%|███████▌  | 3/4 [00:02<00:00,  1.06it/s]
loop param_grid: 100%|██████████| 4/4 [00:04<00:00,  1.13s/it]
loop lags_grid:  33%|███▎      | 1/3 [00:04<00:08,  4.28s/it] 
loop param_grid:   0%|          | 0/4 [00:00<?, ?it/s]
loop param_grid:  25%|██▌       | 1/4 [00:00<00:02,  1.29it/s]
loop param_grid:  50%|█████     | 2/4 [00:02<00:02,  1.20s/it]
loop param_grid:  75%|███████▌  | 3/4 [00:03<00:01,  1.03s/it]
loop param_grid: 100%|██████████| 4/4 [00:04<00:00,  1.25s/it]
loop lags_grid:  67%|██████▋   | 2/3 [00:08<00:04,  4.52s/it] 
loop param_grid:   0%|          | 0/4 [00:00<?, ?it/s]
loop param_grid:  25%|██▌       | 1/4 [00:00<00:02,  1.38it/s]
loop param_grid:  50%|█████     | 2/4 [00:02<00:02,  1.12s/it]
loop param_grid:  75%|███████▌  | 3/4 [00:02<00:00,  1.06it/s]
loop param_grid: 100%|██████████| 4/4 [00:04<00:00,  1.14s/it]
loop lags_grid: 100%|██████████| 3/3 [00:13<00:00,  4.42s/it] 
2021-02-25 09:51:43,075 root       INFO  Refitting `forecaster` using the best found parameters: 
lags: [ 1  2  3  4  5  6  7  8  9 10] 
params: {'max_depth': 10, 'n_estimators': 50}
```


```
      lags	params	metric
6	[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]	{'max_depth': 10, 'n_estimators': 50}	0.023449
4	[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]	{'max_depth': 5, 'n_estimators': 50}	0.025417
7	[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]	{'max_depth': 10, 'n_estimators': 100}	0.025954
5	[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]	{'max_depth': 5, 'n_estimators': 100}	0.026003
1	[1, 2, 3]	{'max_depth': 5, 'n_estimators': 100}	0.028223
0	[1, 2, 3]	{'max_depth': 5, 'n_estimators': 50}	0.030685
3	[1, 2, 3]	{'max_depth': 10, 'n_estimators': 100}	0.031385
2	[1, 2, 3]	{'max_depth': 10, 'n_estimators': 50}	0.038591
8	[1, 2, 3, 20]	{'max_depth': 5, 'n_estimators': 50}	0.048428
9	[1, 2, 3, 20]	{'max_depth': 5, 'n_estimators': 100}	0.049842
10	[1, 2, 3, 20]	{'max_depth': 10, 'n_estimators': 50}	0.051059
11	[1, 2, 3, 20]	{'max_depth': 10, 'n_estimators': 100}	0.052205
```


### Autoregressive + 1 exogenous predictor

```python
# Download data
# ==============================================================================
url = 'https://raw.githubusercontent.com/JoaquinAmatRodrigo/' \
      + 'Estadistica-machine-learning-python/master/data/h2o.csv'
datos = pd.read_csv(url, sep=',')

# Data preprocessing
# ==============================================================================
datos['fecha'] = pd.to_datetime(datos['fecha'], format='%Y/%m/%d')
datos = datos.set_index('fecha')
datos = datos.rename(columns={'x': 'y'})
datos = datos.asfreq('MS')
datos = datos['y']
datos = datos.sort_index()

# Exogenous variable
# ==============================================================================
datos_exog = datos.rolling(window=10, closed='right').mean() + 0.5
datos_exog = datos_exog[10:]
datos = datos[10:]

fig, ax=plt.subplots(figsize=(9, 4))
datos.plot(ax=ax, label='y')
datos_exog.plot(ax=ax, label='exogenous variable')
ax.legend();
```

<p><img src="./images/data_with_exogenous.png"</p>

```python
# Split train-test
# ==============================================================================
steps = 36
datos_train = datos[:-steps]
datos_test  = datos[-steps:]

datos_exog_train = datos_exog[:-steps]
datos_exog_test  = datos_exog[-steps:]
```

```python
# Create and fit forecaster
# ==============================================================================
forecaster = ForecasterAutoreg(
                    regressor = LinearRegression(),
                    lags      = 8
             )

forecaster.fit(y=datos_train, exog=datos_exog_train)

# Predict
# ==============================================================================
steps = 36
predictions = forecaster.predict(steps=steps, exog=datos_exog_test)
# Add datetime index to predictions
predictions = pd.Series(data=predictions, index=datos_test.index)

# Plot
# ==============================================================================
fig, ax=plt.subplots(figsize=(9, 4))
datos_train.plot(ax=ax, label='train')
datos_test.plot(ax=ax, label='test')
predictions.plot(ax=ax, label='predictions')
ax.legend();

# Error prediction
# ==============================================================================
error_mse = mean_squared_error(
                y_true = datos_test,
                y_pred = predictions
            )
print(f"Test error (mse): {error_mse}")
```

```
Test error (mse): 0.020306077140235308
```

<p><img src="./images/prediction_with_exog.png"</p>


```python
# Grid search hiperparameters and lags
# ==============================================================================
forecaster = ForecasterAutoreg(
                regressor=RandomForestRegressor(random_state=123),
                lags=12
             )

# Regressor hiperparameters
param_grid = {'n_estimators': [50, 100],
              'max_depth': [5, 10]}

# Lags used as predictors
lags_grid = [3, 10, [1,2,3,20]]

results_grid = grid_search_forecaster(
                        forecaster  = forecaster,
                        y           = datos_train,
                        exog        = datos_exog_train,
                        param_grid  = param_grid,
                        lags_grid   = lags_grid,
                        steps       = 10,
                        metric      = 'neg_mean_squared_error',
                        initial_train_size    = int(len(datos_train)*0.5),
                        allow_incomplete_fold = False,
                        return_best = True
                    )

# Results grid Search
# ==============================================================================
results_grid
```

### Autoregressive + n exogenous predictors
<br>

```python
# Download data
# ==============================================================================
url = 'https://raw.githubusercontent.com/JoaquinAmatRodrigo/' \
      + 'Estadistica-machine-learning-python/master/data/h2o.csv'
datos = pd.read_csv(url, sep=',')

# Data preprocessing
# ==============================================================================
datos['fecha'] = pd.to_datetime(datos['fecha'], format='%Y/%m/%d')
datos = datos.set_index('fecha')
datos = datos.rename(columns={'x': 'y'})
datos = datos.asfreq('MS')
datos = datos['y']
datos = datos.sort_index()

# Exogenous variables
# ==============================================================================
datos_exog_1 = datos.rolling(window=10, closed='right').mean() + 0.5
datos_exog_2 = datos.rolling(window=10, closed='right').mean() + 1
datos_exog_1 = datos_exog_1[10:]
datos_exog_2 = datos_exog_2[10:]
datos = datos[10:]

fig, ax=plt.subplots(figsize=(9, 4))
datos.plot(ax=ax, label='y')
datos_exog_1.plot(ax=ax, label='exogenous variable 1')
datos_exog_2.plot(ax=ax, label='exogenous variable 2')
ax.legend();

# Split train-test
# ==============================================================================
steps = 36
datos_train = datos[:-steps]
datos_test  = datos[-steps:]

datos_exog = np.column_stack((datos_exog_1.values, datos_exog_2.values))
datos_exog_train = datos_exog[:-steps,]
datos_exog_test  = datos_exog[-steps:,]
```

```python
# Create and fit forecaster
# ==============================================================================
forecaster = ForecasterAutoreg(
                    regressor = LinearRegression(),
                    lags      = 8
             )

forecaster.fit(y=datos_train, exog=datos_exog_train)

# Predict
# ==============================================================================
steps = 36
predictions = forecaster.predict(steps=steps, exog=datos_exog_test)
# Add datetime index
predictions = pd.Series(data=predictions, index=datos_test.index)

# Plot
# ==============================================================================
fig, ax=plt.subplots(figsize=(9, 4))
datos_train.plot(ax=ax, label='train')
datos_test.plot(ax=ax, label='test')
predictions.plot(ax=ax, label='predictions')
ax.legend();

# Error
# ==============================================================================
error_mse = mean_squared_error(
                y_true = datos_test,
                y_pred = predictions
            )
print(f"Test error (mse): {error_mse}")
```

```python
# Grid search hiperparameters and lags
# ==============================================================================
forecaster = ForecasterAutoreg(
                regressor=RandomForestRegressor(random_state=123),
                lags=12
             )

# Regressor hiperparameters
param_grid = {'n_estimators': [50, 100],
              'max_depth': [5, 10]}

# Lags used as predictors
lags_grid = [3, 10, [1,2,3,20]]

results_grid = grid_search_forecaster(
                        forecaster  = forecaster,
                        y           = datos_train,
                        exog        = datos_exog_train,
                        param_grid  = param_grid,
                        lags_grid   = lags_grid,
                        steps       = 10,
                        metric      = 'neg_mean_squared_error',
                        initial_train_size    = int(len(datos_train)*0.5),
                        allow_incomplete_fold = False,
                        return_best = True
                    )

# Results grid Search
# ==============================================================================
results_grid
```

## Author

<a rel="license" href="http://creativecommons.org/licenses/by/4.0/"><img alt="Creative Commons Licence" style="border-width:0" src="https://i.creativecommons.org/l/by/4.0/88x31.png" /></a><br />This work by  Joaquín Amat Rodrigo is licensed under a <a rel="license" href="http://creativecommons.org/licenses/by/4.0/">Creative Commons Attribution 4.0 International License</a>.
