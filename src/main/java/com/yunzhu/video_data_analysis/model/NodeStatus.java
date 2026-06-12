package com.yunzhu.video_data_analysis.model;

/** Lifecycle state for one Agent DAG node. */
public enum NodeStatus {
    PENDING,
    RUNNING,
    SUCCESS,
    FAILED,
    SKIPPED,
    WAITING_APPROVAL
}
