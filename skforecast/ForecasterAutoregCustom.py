################################################################################
#                               skforecast                                     #
#                                                                              #
# This work by Joaquín Amat Rodrigo is licensed under a Creative Commons       #
# Attribution 4.0 International License.                                       #
################################################################################
# coding=utf-8

import typing
from typing import Union, Dict, List, Tuple, Any
import warnings
import logging
import numpy as np
import pandas as pd
import sklearn
import tqdm
from copy import copy

from sklearn.metrics import mean_squared_error
from sklearn.metrics import mean_absolute_error
from sklearn.metrics import mean_absolute_percentage_error


logging.basicConfig(
    format = '%(name)-10s %(levelname)-5s %(message)s', 
    level  = logging.INFO,
)


################################################################################
#                        ForecasterAutoregCustom                               #
################################################################################

class ForecasterAutoregCustom():
    '''
    This class turns any regressor compatible with the scikit-learn API into a
    recursive (multi-step) forecaster with a custom function to create predictors.
    
    Parameters
    ----------
    regressor : any regressor compatible with the scikit-learn API
        An instance of a regressor compatible with the scikit-learn API.
        
    fun_predictors: Callable
        Function that takes a time series window as input and returns a numpy
        ndarray with the predictors associated with that window.
        
    window_size: int
        Size of the window needed by `fun_predictors` to create the predictors.
    
    
    Attributes
    ----------
    regressor : regressor compatible with the scikit-learn API
        An instance of a regressor compatible with the scikit-learn API.
        
    fun_predictors: Callable
        Function that takes a time series window as input and returns a numpy
        ndarray with the predictors associated with that window.
        
    window_size: int
        Size of the window needed by `fun_predictors` to create the predictors.
        
    last_window : pandas Series
        Last window the forecaster has seen during trained. It stores the
        values needed to calculate the lags used to predict the next `step`
        after the training data.
        
    window_size: int
        Size of the window needed to create the predictors. It is equal to
        `max_lag`.
        
    fitted: Bool
        Tag to identify if the regressor has been fitted (trained).
        
    index_type : type
        Index type of the inputused in training.
        
    index_freq : str
        Index frequency of the input used in training.
        
    training_range: pandas Index
        First and last index of samples used during training.
        
    included_exog : bool
        If the forecaster has been trained using exogenous variable/s.
        
    exog_type : type
        Type of exogenous variable/s used in training.
        
    exog_col_names : tuple
        Column names of exog if exog used in training is a pandas DataFrame.
        
    in_sample_residuals: numpy ndarray
        Residuals of the model when predicting training data. Only stored up to
        1000 values.
        
    out_sample_residuals: numpy ndarray
        Residuals of the model when predicting non training data. Only stored
        up to 1000 values.
     
    '''
    
    def __init__(self, regressor, fun_predictors: callable, window_size: int) -> None:
        
        self.regressor            = regressor
        self.create_predictors    = fun_predictors
        self.window_size          = window_size
        self.index_type           = None
        self.index_freq           = None
        self.training_range       = None
        self.last_window          = None
        self.included_exog        = False
        self.exog_type            = None
        self.exog_col_names       = None
        self.in_sample_residuals  = None
        self.out_sample_residuals = None
        self.fitted               = False
        
        if not isinstance(window_size, int):
            raise Exception(
                f'`window_size` must be int, got {type(window_size)}'
            )

        if not callable(fun_predictors):
            raise Exception(
                f'`fun_predictors` must be callable, got {type(fun_predictors)}.'
            )
                
        
    def __repr__(self) -> str:
        '''
        Information displayed when a ForecasterAutoregCustom object is printed.
        '''

        info = (
            f"{'=' * len(str(type(self)))} \n"
            f"{type(self)} \n"
            f"{'=' * len(str(type(self)))} \n"
            f"Regressor: {self.regressor} \n"
            f"Predictors created with:: {self.create_predictors.__name__} \n"
            f"Window size: {self.window_size} \n"
            f"Included exogenous: {self.included_exog} \n"
            f"Type of exogenous variable: {self.exog_type} \n"
            f"Exogenous variables names: {self.exog_col_names} \n"
            f"Training range: {self.training_range.to_list() if self.fitted else None} \n"
            f"Training index type: {str(self.index_type) if self.fitted else None} \n"
            f"Training index frequancy: {self.index_freq if self.fitted else None} \n"
            f"Regressor parameters: {self.regressor.get_params()} \n"
        )

        return info

    
    def create_train_X_y(
        self,
        y: pd.Series,
        exog: Union[pd.Series, pd.DataFrame]=None
    ) -> Tuple[pd.DataFrame, pd.Series]:
        '''
        Create training matrices from univariante time series.
        
        Parameters
        ----------        
        y : pandas Series
            Training time series.
            
        exog : pandas Series, pandas DataFrame, default `None`
            Exogenous variable/s included as predictor/s. Must have the same
            number of observations as `y` and their indexes must be aligned.


        Returns 
        -------
        X_train : pandas DataFrame
            Pandas DataFrame with the training values (predictors).
            
        y_train : pandas Series
            Values (target) of the time series related to each row of `X_train`.
        
        '''
        
        if len(y) < self.window_size + 1:
            raise Exception(
                f'`y` must have as many values as the windows_size needed by '
                f'{self.create_predictors.__name__}. For this Forecaster the '
                f'minimum lenght is {self.window_size + 1}'
            )

        self._check_y(y=y)
        y_values, y_index = self._preproces_y(y=y)
        
        if exog is not None:
            if len(exog) != len(y):
                raise Exception(
                    "`exog` must have same number of samples as `y`."
                )
            self._check_exog(exog=exog)
            exog_values, exog_index = self._preproces_exog(exog=exog)
            if not (exog_index[:len(y_index)] == y_index).all():
                raise Exception(
                ('Different index for `y` and `exog`. They must be equal '
                'to ensure the correct aligment of values.')      
                )
       
        X_train  = []
        y_train  = []

        for i in range(len(y) - self.window_size):

            train_index = np.arange(i, self.window_size + i)
            test_index  = self.window_size + i

            X_train.append(self.create_predictors(y=y_values.iloc[train_index]))
            y_train.append(y_values.iloc[test_index])
        
        X_train = np.vstack(X_train)
        y_train = np.array(y_train)
        col_names_X_train = [f"custom_predictor_{i}" for i in X_train.shape[1]]

        if np.isnan(X_train).any():
            raise Exception(
                f"`create_predictors()` is returning `NaN` values."
            )
        
        if exog is not None:
            col_names_exog = exog.columns if isinstance(exog, pd.DataFrame) else exog.name
            col_names_X_train.extend(col_names_exog)
            # The first `self.max_lag` positions have to be removed from exog
            # since they are not in X_train.
            X_train = np.column_stack((X_train, exog_values[self.max_lag:, ]))

        X_train = pd.DataFrame(
                    data    = X_train,
                    columns = col_names_X_train,
                    index   = y_index[self.max_lag: ]
                  )

        y_train = pd.Series(
                    data  = y_train,
                    index = y_index[self.max_lag: ],
                    name  = 'y'
                 )
                        
        return X_train, y_train

        
    def fit(self, y: Union[np.ndarray, pd.Series],
            exog: Union[np.ndarray, pd.Series, pd.DataFrame]=None) -> None:
        '''
        Training Forecaster.
        
        Parameters
        ----------        
        y : pandas Series
            Training time series.
            
        exog : pandas Series, pandas DataFrame, default `None`
            Exogenous variable/s included as predictor/s. Must have the same
            number of observations as `y` and their indexes must be aligned so
            that y[i] is regressed on exog[i].


        Returns 
        -------
        None
        
        '''
        
        # Reset values in case the forecaster has already been fitted.
        self.index_type           = None
        self.index_freq           = None
        self.last_window          = None
        self.included_exog        = False
        self.exog_type            = None
        self.exog_col_names       = None
        self.in_sample_residuals  = None
        self.out_sample_residuals = None
        self.fitted               = False
        self.training_range       = None
        
        if exog is not None:
            self.included_exog = True
            self.exog_type = type(exog)
            if isinstance(exog, pd.DataFrame):
                self.exog_col_names = exog.columns.to_list()
        
        X_train, y_train = self.create_train_X_y(y=y, exog=exog)      
        self.regressor.fit(X=X_train, y=y_train)
        self.fitted = True
        self.training_range = X_train.index[[0, -1]]
        self.index_type = type(X_train.index)
        if isinstance(X_train.index, pd.DatetimeIndex):
            self.index_freq = X_train.index.freqstr
        else: 
            self.index_freq = X_train.index.step

        residuals = y_train - self.regressor.predict(X_train)
        if len(residuals) > 1000:
            # Only up to 1000 residuals are stored
            residuals = np.random.choice(a=residuals, size=1000, replace=False)                                              
        self.in_sample_residuals = residuals
        
        # The last time window of training data is stored so that predictors in
        # the first iteration of `predict()` can be calculated.
        self.last_window = y_train.iloc[-self.window_size:].copy()


    def _recursive_predict(
        self,
        steps: int,
        last_window: np.array,
        exog: np.array
    ) -> pd.Series:
        '''
        Predict n steps ahead. It is an iterative process in which, each prediction,
        is used as a predictor for the next step.
        
        Parameters
        ----------
        steps : int
            Number of future steps predicted.
            
        last_window : numpy ndarray
            Values of the series used to create the predictors (lags) need in the 
            first iteration of predictiont (t + 1).
            
        exog : numpy ndarray, pandas DataFrame
            Exogenous variable/s included as predictor/s.

        Returns 
        -------
        predictions : numpy ndarray
            Predicted values.
            
        '''

        predictions = np.full(shape=steps, fill_value=np.nan)

        for i in range(steps):
            X = self.create_predictors(y=last_window)
            if np.isnan(X).any():
                raise Exception(
                    f"`create_predictors()` is returning `NaN` values."
                )
            if exog is not None:
                X = np.column_stack((X, exog[i, ].reshape(1, -1)))

            prediction = self.regressor.predict(X)
            predictions[i] = prediction.ravel()[0]

            # Update `last_window` values. The first position is discarded and 
            # the new prediction is added at the end.
            last_window = np.append(last_window[1:], prediction)

        return predictions
        
            
    def predict(
        self,
        steps: int,
        last_window: pd.Series=None,
        exog: Union[pd.Series, pd.DataFrame]=None
    ) -> pd.Series:
        '''
        Predict n steps ahead. It is an recursive process in which, each prediction,
        is used as a predictor for the next step.
        
        Parameters
        ----------
        steps : int
            Number of future steps predicted.
            
        last_window : pandas Series, default `None`
            Values of the series used to create the predictors (lags) need in the 
            first iteration of predictiont (t + 1).
    
            If `last_window = None`, the values stored in` self.last_window` are
            used to calculate the initial predictors, and the predictions start
            right after training data.
            
        exog : pandas Series, pandas DataFrame, default `None`
            Exogenous variable/s included as predictor/s.

        Returns 
        -------
        predictions : pandas Series
            Predicted values.
            
        '''

        self._check_predict_input(
            steps       = steps,
            last_window = last_window, 
            exog        = exog
        )
     
        if exog is not None:
            if isinstance(exog, pd.DataFrame):
                exog_values, exog_index = self._preproces_exog(
                                            exog = exog[self.exog_col_names].iloc[:steps, ]
                                        )
            else: 
                exog_values, exog_index = self._preproces_exog(
                                            exog = exog.iloc[:steps, ]
                                        )
        else:
            exog_values = None
            exog_index = None
        
        if last_window is not None:
            last_window_values, last_window_index = self._preproces_last_window(
                                                        last_window = last_window
                                                    )  
        else:
            last_window_values, last_window_index = self._preproces_last_window(
                                                        last_window = self.last_window
                                                    )
            
        predictions = self._recursive_predict(
                        steps       = steps,
                        last_window = copy(last_window_values),
                        exog        = copy(exog_values)
                      )

        predictions = pd.Series(
                        data  = predictions,
                        index = self._expand_index(
                                    index = last_window_index,
                                    steps = steps
                                ),
                        name = 'pred'
                      )

        return predictions

        return predictions
    
    
    def _estimate_boot_interval(self, steps: int,
                                last_window: Union[np.ndarray, pd.Series]=None,
                                exog: Union[np.ndarray, pd.Series, pd.DataFrame]=None,
                                interval: list=[5, 95], n_boot: int=500,
                                in_sample_residuals: bool=True) -> np.ndarray:
        '''
        Iterative process in which, each prediction, is used as a predictor
        for the next step and bootstrapping is used to estimate prediction
        intervals. This method only returns prediction intervals.
        See predict_intervals() to calculate both, predictions and intervals.
        
        Parameters
        ---------- 
        steps : int
            Number of future steps predicted.
            
        last_window : 1D np.ndarray, pd.Series, default `None`
            Values of the series used to create the predictors need in the first
            iteration of predictiont (t + 1).
    
            If `last_window = None`, the values stored in` self.last_window` are
            used to calculate the initial predictors, and the predictions start
            right after training data.
            
        exog : np.ndarray, pd.Series, pd.DataFrame, default `None`
            Exogenous variable/s included as predictor/s.
            
        n_boot: int, default `100`
            Number of bootstrapping iterations used to estimate prediction
            intervals.
            
        interval: list, default `[5, 100]`
            Confidence of the prediction interval estimated. Sequence of percentiles
            to compute, which must be between 0 and 100 inclusive.
            
        in_sample_residuals: bool, default `True`
            If `True`, residuals from the training data are used as proxy of
            prediction error to create prediction intervals. If `False`, out of
            sample residuals are used. In the latter case, the user shoud have
            calculated and stored the residuals within the forecaster (see
            `set_out_sample_residuals()`).
            

        Returns 
        -------
        predicction_interval : np.array, shape (steps, 2)
            Interval estimated for each prediction by bootstrapping.

        Notes
        -----
        More information about prediction intervals in forecasting:
        https://otexts.com/fpp2/prediction-intervals.html
        Forecasting: Principles and Practice (2nd ed) Rob J Hyndman and
        George Athanasopoulos.
            
        '''
        
        if steps < 1:
            raise Exception(
                f"`steps` must be integer greater than 0. Got {steps}."
            )
            
        if not in_sample_residuals and self.out_sample_residuals is None:
            raise Exception(
                ('out_sample_residuals is empty. In order to estimate prediction '
                'intervals using out of sample residuals, the user shoud have '
                'calculated and stored the residuals within the forecaster (see'
                '`set_out_sample_residuals()`.')
            )
            
        if exog is None and self.included_exog:
            raise Exception(
                f"Forecaster trained with exogenous variable/s. "
                f"Same variable/s must be provided in `predict()`."
            )
            
        if exog is not None and not self.included_exog:
            raise Exception(
                f"Forecaster trained without exogenous variable/s. "
                f"`exog` must be `None` in `predict()`."
            )
        
        if exog is not None:
            self._check_exog(
                exog=exog, ref_type = self.exog_type, ref_shape=self.exog_shape
            )
            exog = self._preproces_exog(exog=exog)
            if exog.shape[0] < steps:
                raise Exception(
                    f"`exog` must have at least as many values as `steps` predicted."
                )
     
        if last_window is not None:
            self._check_last_window(last_window=last_window)
            last_window = self._preproces_last_window(last_window=last_window)
            if last_window.shape[0] < self.window_size:
                raise Exception(
                    f"`last_window` must have as many values as as needed to "
                    f"calculate the predictors ({self.window_size})."
                )
        else:
            last_window = self.last_window.copy()

        boot_predictions = np.full(
                                shape      = (steps, n_boot),
                                fill_value = np.nan,
                                dtype      = float
                           )

        for i in range(n_boot):

            # In each bootstraping iteration the initial last_window and exog 
            # need to be restored.
            last_window_boot = last_window.copy()
            if exog is not None:
                exog_boot = exog.copy()
            else:
                exog_boot = None
                
            if in_sample_residuals:
                residuals = self.in_sample_residuals
            else:
                residuals = self.out_sample_residuals

            sample_residuals = np.random.choice(
                                    a       = residuals,
                                    size    = steps,
                                    replace = True
                               )

            for step in range(steps):  
                
                prediction = self.predict(
                                steps       = 1,
                                last_window = last_window_boot,
                                exog        = exog_boot
                             )
                
                prediction_with_residual  = prediction + sample_residuals[step]
                boot_predictions[step, i] = prediction_with_residual

                last_window_boot = np.append(
                                    last_window_boot[1:],
                                    prediction_with_residual
                                   )
                
                if exog is not None:
                    exog_boot = exog_boot[1:]

        prediction_interval = np.percentile(boot_predictions, q=interval, axis=1)
        prediction_interval = prediction_interval.transpose()
        
        return prediction_interval
    
    
    def predict_interval(self, steps: int, last_window: Union[np.ndarray, pd.Series]=None,
                         exog: Union[np.ndarray, pd.Series, pd.DataFrame]=None,
                         interval: list=[5, 95], n_boot: int=500,
                         in_sample_residuals: bool=True) -> np.ndarray:
        '''
        Iterative process in which, each prediction, is used as a predictor
        for the next step and bootstrapping is used to estimate prediction
        intervals. Both, predictions and intervals, are returned.
        
        Parameters
        ----------   
        steps : int
            Number of future steps predicted.
            
        last_window : 1D np.ndarray, pd.Series, default `None`
            Values of the series used to create the predictors need in the first
            iteration of predictiont (t + 1).
    
            If `last_window = None`, the values stored in` self.last_window` are
            used to calculate the initial predictors, and the predictions start
            right after training data.
            
        exog : np.ndarray, pd.Series, pd.DataFrame, default `None`
            Exogenous variable/s included as predictor/s.
            
        interval: list, default `[5, 100]`
            Confidence of the prediction interval estimated. Sequence of percentiles
            to compute, which must be between 0 and 100 inclusive.
            
        n_boot: int, default `500`
            Number of bootstrapping iterations used to estimate prediction
            intervals.
            
        in_sample_residuals: bool, default `True`
            If `True`, residuals from the training data are used as proxy of
            prediction error to create prediction intervals. If `False`, out of
            sample residuals are used. In the latter case, the user shoud have
            calculated and stored the residuals within the forecaster (see
            `set_out_sample_residuals()`).

        Returns 
        -------
        predictions : np.array, shape (steps, 3)
            Values predicted by the forecaster and their estimated interval.
            Column 0 = predictions
            Column 1 = lower bound interval
            Column 2 = upper bound interval

        Notes
        -----
        More information about prediction intervals in forecasting:
        https://otexts.com/fpp2/prediction-intervals.html
        Forecasting: Principles and Practice (2nd ed) Rob J Hyndman and
        George Athanasopoulos.
            
        '''
        
        if steps < 1:
            raise Exception(
                f"`steps` must be integer greater than 0. Got {steps}."
            )
            
        if not in_sample_residuals and self.out_sample_residuals is None:
            raise Exception(
                ('out_sample_residuals is empty. In order to estimate prediction '
                'intervals using out of sample residuals, the user shoud have '
                'calculated and stored the residuals within the forecaster (see'
                '`set_out_sample_residuals()`.')
            )
            
        if exog is None and self.included_exog:
            raise Exception(
                f"Forecaster trained with exogenous variable/s. "
                f"Same variable/s must be provided in `predict()`."
            )
            
        if exog is not None and not self.included_exog:
            raise Exception(
                f"Forecaster trained without exogenous variable/s. "
                f"`exog` must be `None` in `predict()`."
            )
        
        if exog is not None:
            self._check_exog(
                exog=exog, ref_type = self.exog_type, ref_shape=self.exog_shape
            )
            exog = self._preproces_exog(exog=exog)
            if exog.shape[0] < steps:
                raise Exception(
                    f"`exog` must have at least as many values as `steps` predicted."
                )
     
        if last_window is not None:
            self._check_last_window(last_window=last_window)
            last_window = self._preproces_last_window(last_window=last_window)
            if last_window.shape[0] < self.window_size:
                raise Exception(
                    f"`last_window` must have as many values as as needed to "
                    f"calculate the predictors ({self.window_size})."
                )
        else:
            last_window = self.last_window.copy()
        
        # Since during predict() `last_window` and `exog` are modified, the
        # originals are stored to be used later
        last_window_original = last_window.copy()
        if exog is not None:
            exog_original = exog.copy()
        else:
            exog_original = exog
            
        predictions = self.predict(
                            steps       = steps,
                            last_window = last_window,
                            exog        = exog
                      )

        predictions_interval = self._estimate_boot_interval(
                                    steps       = steps,
                                    last_window = last_window_original,
                                    exog        = exog_original,
                                    interval    = interval,
                                    n_boot      = n_boot,
                                    in_sample_residuals = in_sample_residuals
                                )
        
        predictions = np.column_stack((predictions, predictions_interval))

        return predictions
    
    
    def _check_y(self, y: Union[np.ndarray, pd.Series]) -> None:
        '''
        Raise Exception if `y` is not 1D `np.ndarray` or `pd.Series`.
        
        Parameters
        ----------        
        y : np.ndarray, pd.Series
            Time series values

        '''
        
        if not isinstance(y, (np.ndarray, pd.Series)):
            raise Exception('`y` must be `1D np.ndarray` or `pd.Series`.')
        elif isinstance(y, np.ndarray) and y.ndim != 1:
            raise Exception(
                f"`y` must be `1D np.ndarray` o `pd.Series`, "
                f"got `np.ndarray` with {y.ndim} dimensions."
            )
            
        return
    
    
    def _check_last_window(self, last_window: Union[np.ndarray, pd.Series]) -> None:
        '''
        Raise Exception if `last_window` is not 1D `np.ndarray` or `pd.Series`.
        
        Parameters
        ----------        
        last_window : np.ndarray, pd.Series
            Time series values

        '''
        
        if not isinstance(last_window, (np.ndarray, pd.Series)):
            raise Exception('`last_window` must be `1D np.ndarray` or `pd.Series`.')
        elif isinstance(last_window, np.ndarray) and last_window.ndim != 1:
            raise Exception(
                f"`last_window` must be `1D np.ndarray` o `pd.Series`, "
                f"got `np.ndarray` with {last_window.ndim} dimensions."
            )
            
        return
        
        
    def _check_exog(self, exog: Union[np.ndarray, pd.Series, pd.DataFrame], 
                    ref_type: type=None, ref_shape: tuple=None) -> None:
        '''
        Raise Exception if `exog` is not `np.ndarray`, `pd.Series` or `pd.DataFrame`.
        If `ref_shape` is provided, raise Exception if `ref_shape[1]` do not match
        `exog.shape[1]` (number of columns).
        
        Parameters
        ----------        
        exog : np.ndarray, pd.Series, pd.DataFrame
            Exogenous variable/s included as predictor/s.

        exog_type : type, default `None`
            Type of reference for exog.
            
        exog_shape : tuple, default `None`
            Shape of reference for exog.

        '''
            
        if not isinstance(exog, (np.ndarray, pd.Series, pd.DataFrame)):
            raise Exception('`exog` must be `np.ndarray`, `pd.Series` or `pd.DataFrame`.')
            
        if isinstance(exog, np.ndarray) and exog.ndim > 2:
            raise Exception(
                    f" If `exog` is `np.ndarray`, maximum allowed dim=2. "
                    f"Got {exog.ndim}."
                )
            
        if ref_type is not None:
            
            if ref_type == pd.Series:
                if isinstance(exog, pd.Series):
                    return
                elif isinstance(exog, np.ndarray) and exog.ndim == 1:
                    return
                elif isinstance(exog, np.ndarray) and exog.shape[1] == 1:
                    return
                else:
                    raise Exception(
                        f"`exog` must be: `pd.Series`, `np.ndarray` with 1 dimension "
                        f"or `np.ndarray` with 1 column in the second dimension. "
                        f"Got `np.ndarray` with {exog.shape[1]} columns."
                    )
                    
            if ref_type == np.ndarray:
                if exog.ndim == 1 and ref_shape[1] == 1:
                    return
                elif exog.ndim == 1 and ref_shape[1] > 1:
                    raise Exception(
                        f"`exog` must have {ref_shape[1]} columns. "
                        f"Got `np.ndarray` with 1 dimension or `pd.Series`."
                    )
                elif ref_shape[1] != exog.shape[1]:
                    raise Exception(
                        f"`exog` must have {ref_shape[1]} columns. "
                        f"Got `np.ndarray` with {exog.shape[1]} columns."
                    )

            if ref_type == pd.DataFrame:
                if ref_shape[1] != exog.shape[1]:
                    raise Exception(
                        f"`exog` must have {ref_shape[1]} columns. "
                        f"Got `pd.DataFrame` with {exog.shape[1]} columns."
                    )   
        return
    
        
    def _preproces_y(self, y: Union[np.ndarray, pd.Series]) -> np.ndarray:
        
        '''
        Transforms `y` to 1D `np.ndarray` if it is `pd.Series`.
        
        Parameters
        ----------        
        y :1D np.ndarray, pd.Series
            Time series values

        Returns 
        -------
        y: 1D np.ndarray, shape(samples,)
        '''
        
        if isinstance(y, pd.Series):
            return y.to_numpy(copy=True)
        else:
            return y
        
    def _preproces_last_window(self, last_window: Union[np.ndarray, pd.Series]) -> np.ndarray:
        
        '''
        Transforms `last_window` to 1D `np.ndarray` if it is `pd.Series`.
        
        Parameters
        ----------        
        last_window :1D np.ndarray, pd.Series
            Time series values

        Returns 
        -------
        last_window: 1D np.ndarray, shape(samples,)
        '''
        
        if isinstance(last_window, pd.Series):
            return last_window.to_numpy(copy=True)
        else:
            return last_window
        
        
    def _preproces_exog(self, exog: Union[np.ndarray, pd.Series, pd.DataFrame]) -> np.ndarray:
        
        '''
        Transforms `exog` to `np.ndarray` if it is `pd.Series` or `pd.DataFrame`.
        If 1D `np.ndarray` reshape it to (n_samples, 1)
        
        Parameters
        ----------        
        exog : np.ndarray, pd.Series
            Time series values

        Returns 
        -------
        exog: np.ndarray, shape(samples,)
        '''
        
        if isinstance(exog, pd.Series):
            exog = exog.to_numpy(copy=True).reshape(-1, 1)
        elif isinstance(exog, np.ndarray) and exog.ndim == 1:
            exog = exog.reshape(-1, 1)
        elif isinstance(exog, pd.DataFrame):
            exog = exog.to_numpy(copy=True)
            
        return exog
    
    
    def set_params(self, **params: dict) -> None:
        '''
        Set new values to the parameters of the scikit learn model stored in the
        ForecasterAutoregCustom.
        
        Parameters
        ----------
        params : dict
            Parameters values.

        Returns 
        -------
        self
        
        '''
        
        self.regressor.set_params(**params)
        
    
    def set_out_sample_residuals(self, residuals: np.ndarray, append: bool=True)-> None:
        '''
        Set new values to the attribute `out_sample_residuals`. Out of sample
        residuals are meant to be calculated using observations that did not
        participate in the training process.
        
        Parameters
        ----------
        params : 1D np.ndarray
            Values of residuals. If len(residuals) > 1000, only a random sample
            of 1000 values are stored.
            
        append : bool, default `True`
            If `True`, new residuals are added to the once already stored in the attribute
            `out_sample_residuals`. Once the limit of 1000 values is reached, no more values
            are appended. If False, `out_sample_residuals` is overwrited with the new residuals.
            

        Returns 
        -------
        self
        
        '''
        if not isinstance(residuals, np.ndarray):
            raise Exception(
                f"`residuals` argument must be `1D np.ndarray`. Got {type(residuals)}"
            )
            
        if len(residuals) > 1000:
            residuals = np.random.choice(a=residuals, size=1000, replace=False)
                                 
        if not append or self.out_sample_residuals is None:
            self.out_sample_residuals = residuals
        else:
            free_space = max(0, 1000 - len(self.out_sample_residuals))
            if len(residuals) < free_space:
                self.out_sample_residuals = np.hstack((self.out_sample_residuals, residuals))
            else:
                self.out_sample_residuals = np.hstack((self.out_sample_residuals, residuals[:free_space]))
                

    def get_coef(self) -> np.ndarray:
        '''      
        Return estimated coefficients for the linear regression model stored in
        the forecaster. Only valid when the forecaster has been trained using
        as `regressor: `LinearRegression()`, `Lasso()` or `Ridge()`.
        
        Parameters
        ----------
        self

        Returns 
        -------
        coef : 1D np.ndarray
            Value of the coefficients associated with each predictor.
            Coefficients are aligned so that `coef[i]` is the value associated
            with predictor i returned by `self.create_predictors`.
        
        '''
        
        valid_instances = (sklearn.linear_model._base.LinearRegression,
                          sklearn.linear_model._coordinate_descent.Lasso,
                          sklearn.linear_model._ridge.Ridge
                          )
        
        if not isinstance(self.regressor, valid_instances):
            warnings.warn(
                ('Only forecasters with `regressor` `LinearRegression()`, ' +
                 ' `Lasso()` or `Ridge()` have coef.')
            )
            return
        else:
            coef = self.regressor.coef_
            
        return coef

    
    def get_feature_importances(self) -> np.ndarray:
        '''      
        Return impurity-based feature importances of the model stored in the
        forecaster. Only valid when the forecaster has been trained using
        `regressor=GradientBoostingRegressor()` or `regressor=RandomForestRegressor`.

        Parameters
        ----------
        self

        Returns 
        -------
        feature_importances : 1D np.ndarray
        Impurity-based feature importances associated with each predictor.
        Values are aligned so that `feature_importances[i]` is the value
        associated with predictor i returned by `self.create_predictors`.
        '''

        if not isinstance(self.regressor,
                        (sklearn.ensemble._forest.RandomForestRegressor,
                        sklearn.ensemble._gb.GradientBoostingRegressor)):
            warnings.warn(
                ('Only forecasters with `regressor=GradientBoostingRegressor()` '
                    'or `regressor=RandomForestRegressor`.')
            )
            return
        else:
            feature_importances = self.regressor.feature_importances_

        return feature_importances