import numpy as np
from scipy.signal import savgol_filter
from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class PreprocessResult:
    t_smoothed: np.ndarray
    y_smoothed: np.ndarray
    y_original: np.ndarray
    noise_std: float
    noise_level: float
    signal_to_noise: float
    smooth_method: str
    window_size: int
    poly_order: int


def estimate_noise_std(y: np.ndarray) -> float:
    if len(y) < 5:
        return 0.0
    
    diff = np.diff(y)
    mad = np.median(np.abs(diff - np.median(diff)))
    sigma = 1.4826 * mad / np.sqrt(2)
    return float(sigma)


def estimate_noise_level(y: np.ndarray) -> Tuple[float, float]:
    noise_std = estimate_noise_std(y)
    data_range = np.max(y) - np.min(y)
    
    if data_range < 1e-10:
        return noise_std, 1.0
    
    noise_level = noise_std / data_range
    return noise_std, float(noise_level)


def moving_average(y: np.ndarray, window_size: int = 5) -> np.ndarray:
    if window_size % 2 == 0:
        window_size += 1
    
    if window_size >= len(y):
        return y.copy()
    
    kernel = np.ones(window_size) / window_size
    smoothed = np.convolve(y, kernel, mode='same')
    
    edge = window_size // 2
    smoothed[:edge] = y[:edge]
    smoothed[-edge:] = y[-edge:]
    
    return smoothed


def savgol_smooth(
    y: np.ndarray,
    window_size: Optional[int] = None,
    poly_order: int = 2
) -> Tuple[np.ndarray, int, int]:
    n = len(y)
    
    if n < 5:
        return y.copy(), n, 1
    
    if window_size is None:
        noise_std, noise_level = estimate_noise_level(y)
        if noise_level > 0.15:
            window_size = min(15, max(5, n // 8))
        elif noise_level > 0.05:
            window_size = min(11, max(5, n // 12))
        else:
            window_size = min(7, max(5, n // 20))
    
    if window_size % 2 == 0:
        window_size += 1
    
    if window_size <= poly_order:
        window_size = poly_order + 1
        if window_size % 2 == 0:
            window_size += 1
    
    if window_size >= n:
        window_size = n - 1 if n % 2 == 0 else n - 2
        if window_size <= poly_order:
            return y.copy(), 1, 1
    
    try:
        smoothed = savgol_filter(y, window_size, poly_order, mode='interp')
        return smoothed, window_size, poly_order
    except Exception:
        try:
            smoothed = savgol_filter(y, window_size, 1, mode='interp')
            return smoothed, window_size, 1
        except Exception:
            return y.copy(), 1, 1


def auto_smooth(
    t: np.ndarray,
    y: np.ndarray
) -> PreprocessResult:
    y = np.asarray(y, dtype=float)
    t = np.asarray(t, dtype=float)
    
    if len(y) < 5:
        noise_std, noise_level = estimate_noise_level(y)
        snr = 0.0 if noise_std < 1e-10 else (np.std(y) / noise_std)
        return PreprocessResult(
            t_smoothed=t,
            y_smoothed=y.copy(),
            y_original=y.copy(),
            noise_std=noise_std,
            noise_level=noise_level,
            signal_to_noise=float(snr),
            smooth_method="none",
            window_size=1,
            poly_order=1
        )
    
    noise_std, noise_level = estimate_noise_level(y)
    signal_std = np.std(y)
    snr = 0.0 if noise_std < 1e-10 else float(signal_std / noise_std)
    
    if noise_level < 0.02:
        method = "none"
        y_smooth = y.copy()
        used_window = 1
        used_poly = 1
    elif noise_level < 0.1:
        method = "savgol_light"
        y_smooth, used_window, used_poly = savgol_smooth(y, poly_order=2)
    elif noise_level < 0.25:
        method = "savgol_medium"
        y_smooth, used_window, used_poly = savgol_smooth(y, poly_order=3)
    else:
        method = "savgol_heavy"
        y_smooth, used_window, used_poly = savgol_smooth(y, poly_order=2)
        y_smooth = moving_average(y_smooth, window_size=max(3, used_window // 2))
    
    return PreprocessResult(
        t_smoothed=t,
        y_smoothed=y_smooth,
        y_original=y.copy(),
        noise_std=noise_std,
        noise_level=noise_level,
        signal_to_noise=snr,
        smooth_method=method,
        window_size=used_window,
        poly_order=used_poly
    )


def estimate_derivatives(
    t: np.ndarray,
    y: np.ndarray,
    smooth: bool = True
) -> Tuple[np.ndarray, np.ndarray]:
    if smooth and len(y) >= 5:
        y_smooth, _, _ = savgol_smooth(y)
    else:
        y_smooth = y.copy()
    
    n = len(y_smooth)
    dy = np.zeros(n)
    
    if n < 3:
        if n == 2:
            dt = t[1] - t[0]
            if dt > 0:
                dy[:] = (y_smooth[1] - y_smooth[0]) / dt
        return dy, np.zeros(n)
    
    dt = np.diff(t)
    if np.any(dt <= 0):
        dt = np.where(dt <= 0, 1e-10, dt)
    
    dy[0] = (y_smooth[1] - y_smooth[0]) / dt[0]
    for i in range(1, n - 1):
        h1 = dt[i - 1]
        h2 = dt[i]
        dy[i] = (y_smooth[i + 1] - y_smooth[i - 1]) / (h1 + h2) * 2
    dy[-1] = (y_smooth[-1] - y_smooth[-2]) / dt[-1]
    
    if n >= 5 and smooth:
        dy, _, _ = savgol_smooth(dy)
    
    d2y = np.zeros(n)
    if n >= 3:
        d2y[0] = (dy[1] - dy[0]) / dt[0]
        for i in range(1, n - 1):
            h1 = dt[i - 1]
            h2 = dt[i]
            d2y[i] = (dy[i + 1] - dy[i - 1]) / (h1 + h2) * 2
        d2y[-1] = (dy[-1] - dy[-2]) / dt[-1]
    
    return dy, d2y
