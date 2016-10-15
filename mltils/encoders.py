# pylint: disable=missing-docstring, import-error
from __future__ import print_function

import numpy as np
from tqdm import tqdm
from sklearn.preprocessing import LabelEncoder, OneHotEncoder
from scipy import sparse

from .utils import validate_is_data_frame, _print


class DummyEncoder(object):
    # pylint: disable=too-many-instance-attributes, too-many-arguments
    def __init__(self, sps_trhsld=0, sep='_', verbose=False, rpl_num=-999,
                 rpl_str='__unknown__', rpl_nan_cat='NaN'):
        self.sps_trhsld = sps_trhsld
        self.rpl_num = rpl_num
        self.rpl_str = rpl_str
        self.rpl_nan_cat = rpl_nan_cat
        self.sep = sep
        self.verbose = verbose
        self.variables = None
        self.cat_vars = None
        self.num_vars = None
        self.var_values = {}
        self.lencs = {}
        self.ohe = OneHotEncoder(handle_unknown='ignore', sparse=True)
        self.var_names = []

    def fit(self, data):
        validate_is_data_frame(data)
        self.variables = data.columns
        self.cat_vars = data.select_dtypes(include=['category', 'object']).columns
        self.num_vars = np.setdiff1d(self.variables, self.cat_vars)

        data = data.copy()
        if self.sps_trhsld > 0:
            if self.verbose:
                _print('Removing sparse values...')
                var_itr = tqdm(self.cat_vars)
            else:
                var_itr = self.cat_vars
            for var in var_itr:
                var_count = data[var].value_counts()
                sps_values = var_count.index[var_count <= self.sps_trhsld]
                sps_rows = data[var].isin(sps_values)
                if sps_rows.any():
                    rpl_val = self._rpl_val_for(data[var])
                    data.loc[sps_rows, var] = rpl_val

        if self.verbose:
            _print('Encoding as integers...')
            var_itr = tqdm(self.cat_vars)
        else:
            var_itr = self.cat_vars
        for var in var_itr:
            data = self.fill_na(data, var)
            unique_vals = set(data[var].unique())
            self.var_values[var] = unique_vals
            rpl_val = self._rpl_val_for(data[var])
            values = np.concatenate([data[var].values, [rpl_val]])
            lenc = LabelEncoder().fit(values)
            self.lencs[var] = lenc
            data.loc[:, var] = lenc.transform(data[var])
            self.var_names.extend(
                '%s%s%s' % (var, self.sep, str(value))
                for value in sorted(unique_vals)
            )
        self.var_names.extend(self.num_vars)

        if self.verbose:
            _print('Fitting one hot enconder...')
        self.ohe.fit(data[self.cat_vars])
        if self.verbose:
            _print('Done!')
        return self

    def transform(self, data):
        validate_is_data_frame(data)
        if not data.columns.equals(self.variables):
            raise ValueError('Unexpected variables found!')

        data = data.copy()
        if self.verbose:
            _print('Encoding unknown values...')
            var_itr = tqdm(self.cat_vars)
        else:
            var_itr = self.cat_vars
        for var in var_itr:
            data = self.fill_na(data, var)
            unique_vals = self.var_values[var]
            unknown_mask = ~(data[var].isin(unique_vals).values)
            if unknown_mask.any():
                rpl_val = self._rpl_val_for(data[var])
                data.loc[unknown_mask, var] = rpl_val

        if self.verbose:
            _print('Encoding as integers...')
            var_itr = tqdm(self.cat_vars)
        else:
            var_itr = self.cat_vars
        for var in var_itr:
            lenc = self.lencs[var]
            data.loc[:, var] = lenc.transform(data[var])

        ohe_enc = self.ohe.transform(data[self.cat_vars])
        num_data = data[self.num_vars]
        return sparse.hstack([ohe_enc, num_data], format='csr')

    def fit_transform(self, data):
        self.fit(data)
        return self.transform(data)

    def fill_na(self, data, var):
        null_mask = data[var].isnull()
        if null_mask.any():
            data.loc[null_mask, var] = self.rpl_nan_cat
        return data

    def _rpl_val_for(self, values):
        if values.dtype == 'object':
            return self.rpl_str
        else:
            return self.rpl_num
