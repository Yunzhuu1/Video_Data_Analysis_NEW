package com.yunzhu.video_data_analysis.model;

/** Top-level lifecycle state for one analysis request. */
public enum RunStatus {
    RUNNING,
    SUCCESS,
    FAILED,
    CANCELED,
    WAITING_APPROVAL
}
