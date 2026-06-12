package com.yunzhu.video_data_analysis.tool;

import com.yunzhu.video_data_analysis.dto.SqlExecuteRequest;
import com.yunzhu.video_data_analysis.service.SqlExecutionService;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.stereotype.Component;

/**
 * 用于对 video_data_analysis 数据库执行SQL SELECT查询的工具。
 * AI模型使用此工具查询数据进行分析。
 * <p>
 * 安全性：只允许SELECT语句。所有其他SQL操作都被拒绝。
 * 行限制通过 {@link java.sql.Statement#setMaxRows(int)} 在JDBC驱动级别强制执行。
 * 错误以字符串形式返回给AI模型，以便它可以自我修正。
 */
@Component
public class SqlExecutionTool {

    private final SqlExecutionService sqlExecutionService;

    public SqlExecutionTool(SqlExecutionService sqlExecutionService) {
        this.sqlExecutionService = sqlExecutionService;
    }

    /**
     * 对数据库执行SQL SELECT语句。
     * 行限制 ({@value #MAX_ROWS}) 在JDBC驱动层强制执行以防止OOM。
     * 只允许SELECT；尝试执行DDL/DML将被立即拒绝。
     * <p>
     * <b>预验证：</b> 在执行前运行 {@code EXPLAIN <sql>} 以捕获
     * schema级别的错误（不存在的表、列），而无需数据开销。
     * 捕获的异常以字符串形式返回，以便AI可以自我修正。
     *
     * @param sql 要执行的SQL SELECT语句
     * @return 格式化的查询结果作为包含行数 and 数据的字符串，
     * 或如果查询失败则返回错误消息
     */
    @Tool(description = """
            Execute a SQL SELECT statement on the video_data_analysis MySQL database.
            Returns query results as a string (max 100 rows).
            Only SELECT queries are permitted; UPDATE, DELETE, DROP, INSERT, ALTER, CREATE,
            TRUNCATE, REPLACE, CALL and other DDL/DML statements will be rejected.
            Use this tool to query user behavior data, dimension tables, and metric definitions.
            If the query returns an error, analyze the error message, fix the SQL, and retry (up to 3 times).
            """)
    public String executeSql(
            @ToolParam(description = "The SQL SELECT statement to execute. Must start with SELECT.") String sql) {
        return sqlExecutionService.execute(SqlExecuteRequest.toolRequest(sql)).toToolResponse();
    }
}
