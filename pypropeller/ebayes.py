import numpy as np
from scipy.stats import t, f, chi2
from statsmodels.nonparametric.smoothers_lowess import lowess
from pypropeller.utils import *
from pypropeller.fitFDist import fit_f_dist_robust, fit_f_dist


def ebayes(fit, proportion=0.01, stdev_coef_lim=[0.1, 4], robust=False, winsor_tail_p=[0.05,0.1]):  # Done
    """Applying empirical bayes method to compute moderated t- and f-statistics for each
    cluster to determine significant changes in composition.

    :param dict fit: Dictionary of fitted linear models for each cluster, resulting from lm_fit.
    :param float proportion: Expected proportion of differentiated clusters , defaults to 0.01
    :param list stdev_coef_lim: Assumed upepr and lower limit for standard deviation, defaults to [0.1, 4]
    :param bool robust: Apply robust method against outliers to estimate of var and df prior, defaults to False
    :param list winsor_tail_p: Limits for winsorization; this will set outliers below min/max percentile
    to the value at min/max percentile, defaults to [0.05,0.1], defaults to [0.05,0.1]
    :raises ValueError: _description_
    :raises ValueError: _description_
    :raises ValueError: _description_
    :return dict: Dictionary with computed statistics.
    """
    stdev_coef_lim = np.array(stdev_coef_lim)
    coefficients = fit['coefficients']  # beta
    sigma = fit['sigma']  # sigma
    stdev = fit['stdev']  # standard deviation (stdev.unscaled in R's version)
    df_residual = fit['df_residual']
    # checks
    if not coefficients.any() or not sigma.any() or not stdev.any() or not df_residual.any():
        raise ValueError("No data!")
    if np.all(df_residual==0):
        raise ValueError("No residual degrees of freedom!")
    if np.all(~np.isfinite(sigma)):
        raise ValueError("No finite residual standard deviation!")
    covariate = None
    n_clusters = len(coefficients)

    # moderated t statistics
    var_prior, var_post, df_prior = squeeze_var(sigma**2, df_residual, robust=robust, winsor_tail_p=winsor_tail_p)
    res = {'s2_prior': var_prior, 's2_post': var_post, 'df_prior': df_prior}
    res['t'] = coefficients / stdev / np.reshape(np.sqrt(res['s2_post']), (n_clusters,1))
    df_total = df_residual + df_prior
    df_pooled = np.nansum(df_residual)
    df_total = pmin(df_total, df_pooled)
    res['df_total'] = df_total
    res['p_value'] = 2*t.cdf(-abs(res["t"]), df=np.reshape(df_total, (len(res["t"]),1)))
    #stdev_unscaled = fit['ssr'] / np.sqrt(res['s2_post'])  # Sum of squared residuals devided by square root of post variance
    
    # B-statistics
    var_prior_lim = stdev_coef_lim**2/res['s2_prior']
    res['var_prior'] = tmixture_matrix(res['t'],stdev,df_total,proportion,var_prior_lim)
    if np.any(np.isnan(res['var_prior'])):
        res['var_prior'][np.isnan(res['var_prior'])] = 1 / res['s2_prior']
        print("Estimation of var_prior failed - set to default value")
    r = np.outer(np.repeat(1, len(res['t'])), res['var_prior'])
    r = (stdev**2 + r) / stdev**2
    t2 = res['t']**2
    inf_df = res['df_prior'] > 10**6
    if any(inf_df):
        kernel = t2 * (1-1/r) / 2
        if any(~inf_df):
            t2_f = t2[~inf_df]
            r_f = r[~inf_df]
            df_total_f = df_total[~inf_df]
            kernel[~inf_df] = (1 + df_total_f[:,np.newaxis]) / 2*np.log((t2_f+df_total_f[:,np.newaxis]) / (t2_f/r_f+df_total_f[:,np.newaxis]))
    else:
        kernel = (1+df_total[:,np.newaxis]) / 2*np.log((t2+df_total[:,np.newaxis]) / (t2/r+df_total[:,np.newaxis]))
    res['lods'] = np.log(proportion/(1-proportion)) - np.log(r)/2 + kernel
        
    fit['df_prior'] = df_prior
    fit['s2_prior'] = res['s2_prior']
    fit['var_prior'] = res['var_prior']
    fit['proportion'] = proportion
    fit['s2_post'] = res['s2_post']
    fit['p_value'] = res['p_value']
    fit['t'] = res['t']
    fit['df_total'] = res['df_total']
    fit['lods'] = res['lods']
    if not fit['design'].empty and is_fullrank(fit['design']):
        F_stat = classify_tests_f(fit)
        fit['F'] = F_stat
        #fit['F'] = F_stat['stat']
        df1 = F_stat['df1']
        df2 = F_stat['df2']
        if df2 > 1e6: 
            fit['F']['F_p_value'] = 1 - chi2.cdf(df1*fit['F']['stat'], df=df1)  # to calculate upper tail [x,inf) since cdf calculates lower tail [0,x]
        else:
            fit['F']['F_p_value'] = 1 - f.cdf(fit['F'], df1, df2)

    return fit


def squeeze_var(var, df, covariate=None, robust=False, winsor_tail_p=[0.05,0.1]):  # DONE
    """Apply empirical bayes method to squeeze posterior variances, given hyperparamters
    from fitting a F distribution to data.

    :param numpy.ndarray var: List of variances resulting from linear model fitting.
    :param np.ndarray df: List of degrees of freedom resulting from linear model fitting.
    :param covariate: defaults to None.
    :param bool robust: Apply robust empirical bayes method, defaults to False
    :param list winsor_tail_p: Limits for winsorization; this will set outliers below min/max percentile
    to the value at min/max percentile, defaults to [0.05,0.1].
    :raises ValueError: When empty var list is given.
    :raises ValueError: When lengths of var and df differ.
    :return float: Estimated var prior, df prior and adjusted var post.
    """
    winsor_tail_p = np.array(winsor_tail_p)
    n = len(var)
    if n == 0:
        raise ValueError("var list is empty!")
    if n == 1:
        var_post = var
        var_prior = var
        df_prior = 0
        return var_post, var_prior, df_prior
    if not isinstance(df, np.ndarray):
        df = np.array([df]*n)
    if len(df) == 1:
        df = np.repeat(df, n)
    if len(df) != n:
        raise ValueError("length of var and df differ!")
    if len(df) > 1:
        var[df==0] = 0
    if robust:
        fit = fit_f_dist_robust(var, df, covariate, winsor_tail_p)
        df_prior = fit['df2_shrunk']
    else:
        fit = fit_f_dist(var, df1=df, covariate=covariate)
        df_prior = fit['df2']
    if not isinstance(df_prior, np.ndarray):
        df_prior = np.array([df_prior])
    if not any(df_prior) or any(np.isnan(df_prior)):
        print("Could not estimate prior!")
        return None
    var_prior = fit['scale']
    is_fin = np.isfinite(df_prior)
    if is_fin.all():
        var_post = (df*var + df_prior*var_prior) / (df + df_prior)
    # From here, at least some df_prior are infinite
    # For infinite df_prior, return var_prior
    if not isinstance(var_prior, np.ndarray):
        var_prior = np.array([var_prior])
    if len(var_prior) == n:
        var_post = var_prior
    else:
        var_post = np.resize(var_prior, n)
    # Maybe some df.prior are finite
    if is_fin.any():
        i = np.where(is_fin)
        if len(df) > 1: df = df[i]
        df_prior_fin = df_prior[i]
        var_post[i] = (df*var[i] + df_prior_fin*var_post[i]) / (df + df_prior_fin)
    
    return var_prior, var_post, df_prior


def tmixture_matrix(t_stat, stdev_unscaled, df, proportion, v0_lim=np.array([])):  # DONE
    """Estimate the prior variance of the coefficients.

    :param numpy.ndarray t_stat: T-statistics
    :param numpy.ndarray stdev_unscaled: Standard deviations resulting from linear model fitting.
    :param numpy.ndarray df: Degrees of freedom resulting from linear model fitting.
    :param float proportion:
    :param numpy.ndarray v0_lim: Upper and lower limitsfor estimated standard deviations, defaults to np.array([])
    :raises ValueError: _description_
    :raises ValueError: _description_
    :return numpy.ndarray: Estimnated v0 values
    """
    if t_stat.shape != stdev_unscaled.shape:
        raise ValueError("Shape of t_stat and stdev_unscaled do not match! ")
        #return None
    if v0_lim.any() and len(v0_lim)!=2:
        raise ValueError("Length of v0_lim must be 2!")
        #return None
    n_coef = t_stat.shape[-1]  # number of columns or conditions
    v0 = np.repeat(0, n_coef)
    for i in range(n_coef):
        v0[i] = tmixture_vector(t_stat[:,i],stdev_unscaled[:,i],df,proportion,v0_lim)
    
    return v0


def tmixture_vector(tstat, stdev_unscaled, df, proportion, v0_lim=np.array([])):  # DONE
    """Estimate scale factor in mixture of two t-distributions. This and tmixture_matrix
    function are used to estimate standard devitaions for clusters.

    :param numpy.ndarray t_stat: T-statistics
    :param numpy.ndarray stdev_unscaled: Standard deviations resulting from linear model fitting.
    :param numpy.ndarray df: Degrees of freedom resulting from linear model fitting.
    :param float proportion:
    :param numpy.ndarray v0_lim: Upper and lower limitsfor estimated standard deviations, defaults to np.array([])
    :return float: Estimated v0 value.
    """
    if np.isnan(tstat).any():
        o = ~np.isnan(tstat)
        tstat = tstat[o]
        stdev_unscaled = stdev_unscaled[o]
        df = df[o]
    n_clusters = len(tstat)
    n_target = int(np.ceil(proportion/2*n_clusters))
    if n_target < 1: return np.nan
    # If ntarget is v small, ensure p at least matches selected proportion
    # This ensures ptarget < 1
    p = max(n_target/n_clusters, proportion)

    tstat = np.absolute(tstat)
    max_df = max(df)
    i = df < max_df
    if i.any():
        tail_p = 1 - t.logcdf(tstat[i], df[i])  # upper tail
        tstat[i] = np.log(1 - t.ppf(tail_p, max_df))
        df[i] = max_df
    # Select top statistics
    o = np.argsort(tstat)[::-1][0:n_target]  # in decreasing order
    tstat = tstat[o]
    v1 = stdev_unscaled[o]**2
    # Compare to order statistics
    r = np.arange(1, n_target+1)
    p0 = 2*(1 - t.cdf(tstat, max_df))
    p_target = ((r-0.5)/n_clusters - (1-p)*p0) / p
    v0 = np.resize(0., n_target)
    pos = p_target > p0
    if pos.any():
        q_target = t.ppf(1 - p_target[pos]/2, max_df)  # upper tail
        v0[pos] = v1[pos]*((tstat[pos]/q_target)**2 - 1)
    if v0_lim.any():
        v0 = pmin(pmax(v0, v0_lim[0]), v0_lim[1])

    # old method
    # ttarget = np.quantile(tstat, (n_clusters-n_target)/(n_clusters-1))
    # top = tstat >= ttarget
    # tstat = tstat[top]
    # v1 = stdev_unscaled[top]**2
    # df = df[top]
    # r = n_target - rankdata(tstat) + 1
    # p0 = t.cdf(-tstat, df=df)
    # p_target = ((r-0.5) / 2 / n_clusters - (1-p) * p0) / p
    # pos = p_target > p0
    # v0 = np.repeat(0, n_target)
    # if pos.any():
    #     q_target = t.ppf(p_target[pos], df=df[pos])
    #     v0[pos] = v1[pos]*((tstat[pos]/q_target)**2 -1)
    # if v0_lim.any():
    #     v0 =  pmin(pmax(v0, v0_lim[0]), v0_lim[1])
    
    return np.mean(v0)


def classify_tests_f(fit, df=np.Inf):  # DONE
    """Use F-tests to classify vectors of t-test statistics into outcomes.
    Used to classify each cluster into up, down or not significantly changing
    depending on related t-tests.
    By Gordon Smyth, adapted from the R Limma package.

    :param dict fit: The result from running lm_fit.
    :param df: Degrees of freedom, defaults to np.Inf
    :param float p_value: defaults to 0.01
    :return dict: F-statistics
    """
    f_stat = {}
    # Check for and adjust any coefficient variances exactly zero (usually caused by an all zero contrast)
    n = fit['cov_coef'].shape[0]
    i = np.arange(0, n) + n*np.arange(0, n)
    cov_coef = np.array(fit['cov_coef'])
    if min(cov_coef.flat[i]) == 0:
        j = i[cov_coef.flat[i] == 0]
        fit['cov_coef'][j] = 1
    cor_matrix = cov_to_corr(fit['cov_coef'])

    tstat = fit['t']
    n_clusters = fit['t'].shape[0]
    n_tests = fit['t'].shape[1]

    if n_tests == 1:
        f_stat['stat'] = tstat**2
        f_stat['df1'] = 1
        f_stat['df2'] = df
        return f_stat
    
    e_values, e_vectors = np.linalg.eig(cor_matrix)  # calculate eigenvalues and eigenvectors
    r = sum(e_values/e_values[0] > 1e-8)  # degrees of freedom
    Q = matvec(e_vectors[:,0:r], 1/np.sqrt(e_values[0:r])/np.sqrt(r))
    f_stat['stat'] = (tstat @ Q)**2 @ np.ones((r,1))
    f_stat['df1'] = r
    f_stat['df2'] = df

    return f_stat
    