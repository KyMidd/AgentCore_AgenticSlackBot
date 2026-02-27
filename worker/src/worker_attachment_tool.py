"""
Response Enhancement Tools for Strands Agent

Provides tools for file attachments and additional messages that extend
the agent's ability to respond beyond a single text message.
"""

from strands import tool
from typing import Callable, Optional


def build_attachment_tool(attachments_list: list) -> Callable:
    """
    Build file attachment tool bound to a specific attachments list.

    Args:
        attachments_list: List to collect file attachments for upload

    Returns:
        Tool function for creating file attachments
    """

    @tool
    def create_file_attachment(
        filename: str,
        content: str,
        title: Optional[str] = None,
    ) -> dict:
        """
        Create a file attachment to upload to the Slack thread.

        Use this tool when content is better served as a downloadable file
        rather than inline text. Ideal use cases:
        - Code scripts longer than 30 lines
        - CSV or tabular data
        - JSON/YAML configuration files
        - Structured documents or reports

        Do NOT use this tool for:
        - Short code snippets that fit naturally in the text response
        - Simple text that can be read inline

        Always include a summary or explanation in the text response
        alongside any attachment to provide context.

        Args:
            filename: Name of the file (including extension, e.g., "script.py" or "data.csv")
            content: Full content of the file as a string
            title: Optional descriptive title for the file (defaults to filename)

        Returns:
            Dictionary with status indicating success or failure
        """
        try:
            # Validate inputs
            if not filename or not filename.strip():
                return {
                    "status": "error",
                    "content": [{"text": "filename is required and cannot be empty."}],
                }

            if not content or not content.strip():
                return {
                    "status": "error",
                    "content": [{"text": "content is required and cannot be empty."}],
                }

            # Use title if provided, otherwise use filename
            effective_title = title if title else filename

            # Append attachment to the list
            attachments_list.append(
                {
                    "filename": filename.strip(),
                    "content": content,
                    "title": effective_title,
                }
            )

            return {
                "status": "success",
                "content": [
                    {
                        "text": f"File attachment '{filename}' created successfully and will be uploaded to the thread."
                    }
                ],
            }

        except Exception as e:
            return {
                "status": "error",
                "content": [{"text": f"Failed to create file attachment: {str(e)}"}],
            }

    return create_file_attachment


def build_additional_message_tool(messages_list: list) -> Callable:
    """
    Build additional message tool bound to a shared messages list.

    Args:
        messages_list: List to collect additional messages for posting

    Returns:
        Tool function for sending additional messages
    """

    @tool
    def send_additional_message(
        message_text: str,
    ) -> dict:
        """
        Queue an additional message to be posted in the Slack thread after your primary response.

        Use this tool when your response needs to be split across multiple messages:
        - Response would exceed Slack's message size limit (~350 words)
        - Logically separate sections that benefit from distinct messages
        - Follow-up context or supplementary information

        Do NOT overuse this tool. Most responses should be a single message.
        Your primary response should be self-contained and complete on its own.
        Additional messages provide supplementary detail.

        You may call this tool multiple times. Messages will be posted in order.

        Args:
            message_text: The text content of the additional message. Must be non-empty.
                         Supports Slack formatting (single asterisks for bold, etc.).

        Returns:
            Dictionary with status indicating success or failure
        """
        try:
            if not message_text or not message_text.strip():
                return {
                    "status": "error",
                    "content": [
                        {"text": "message_text is required and cannot be empty."}
                    ],
                }

            messages_list.append({"text": message_text})

            return {
                "status": "success",
                "content": [
                    {
                        "text": f"Additional message queued (message #{len(messages_list)}). It will be posted after your primary response."
                    }
                ],
            }

        except Exception as e:
            return {
                "status": "error",
                "content": [{"text": f"Failed to queue additional message: {str(e)}"}],
            }

    return send_additional_message


def build_chart_tool(attachments_list: list) -> Callable:
    """
    Build chart generation tool bound to a specific attachments list.

    Generates PNG chart images using matplotlib and appends them as
    binary attachments to the shared attachments_list for Slack upload.

    Args:
        attachments_list: List to collect file attachments (shared with build_attachment_tool)

    Returns:
        Tool function for creating chart images
    """

    @tool
    def create_chart(
        chart_type: str,
        data: str,
        title: str,
        filename: str,
        x_label: Optional[str] = None,
        y_label: Optional[str] = None,
        legend_labels: Optional[str] = None,
        colors: Optional[str] = None,
        stacked: bool = False,
        sort_descending: bool = False,
    ) -> dict:
        """
        Generate a chart or graph as a PNG image and attach it to the Slack thread.

        Use this tool to create visual data representations. The chart is rendered
        as a PNG image and uploaded as a file attachment.

        Supported chart types and their data formats:

        bar / line:
          data = '{"labels": ["Q1","Q2","Q3"], "datasets": [{"name": "Revenue", "values": [10,25,18]}]}'
          Multiple datasets are supported for grouped/stacked bars or multi-line charts.

        pie:
          data = '{"labels": ["Critical","High","Medium"], "values": [5,12,30]}'

        scatter:
          data = '{"datasets": [{"name": "Series A", "x": [1,2,3], "y": [4,5,6]}]}'

        heatmap:
          data = '{"x_labels": ["Mon","Tue"], "y_labels": ["AM","PM"], "values": [[1,2],[3,4]]}'

        table:
          data = '{"headers": ["Service","Uptime"], "rows": [["API","99.9%"],["DB","99.5%"]]}'

        Args:
            chart_type: Type of chart — "bar", "line", "pie", "scatter", "heatmap", or "table"
            data: JSON string containing chart data (see formats above)
            title: Chart title displayed at the top
            filename: Output filename (e.g., "revenue_chart.png")
            x_label: Optional label for the x-axis
            y_label: Optional label for the y-axis
            legend_labels: Optional JSON array string of legend labels (e.g., '["Series A", "Series B"]')
            colors: Optional JSON array string of hex color codes (e.g., '["#FF6B6B", "#4ECDC4"]')
            stacked: If true, render stacked bar chart (bar type only)
            sort_descending: If true, sort data values in descending order

        Returns:
            Dictionary with status indicating success or failure
        """
        import io
        import json

        try:
            # Validate chart_type
            valid_types = ("bar", "line", "pie", "scatter", "heatmap", "table")
            if chart_type not in valid_types:
                return {
                    "status": "error",
                    "content": [
                        {
                            "text": f"Invalid chart_type '{chart_type}'. Must be one of: {', '.join(valid_types)}"
                        }
                    ],
                }

            # Parse data JSON
            try:
                chart_data = json.loads(data)
            except json.JSONDecodeError as e:
                return {
                    "status": "error",
                    "content": [{"text": f"Invalid JSON in data parameter: {str(e)}"}],
                }

            # Parse optional JSON arrays
            color_list = None
            if colors:
                try:
                    color_list = json.loads(colors)
                except json.JSONDecodeError as e:
                    return {
                        "status": "error",
                        "content": [
                            {
                                "text": f"Invalid JSON in colors parameter: {str(e)}. "
                                "Expected a JSON array of strings, e.g. "
                                '["#4ECDC4", "#FF6B6B"].'
                            }
                        ],
                    }

                if (
                    not isinstance(color_list, list)
                    or not color_list
                    or not all(isinstance(c, str) and c.strip() for c in color_list)
                ):
                    return {
                        "status": "error",
                        "content": [
                            {
                                "text": "colors must be a non-empty JSON array of non-empty strings."
                            }
                        ],
                    }

            legend_list = None
            if legend_labels:
                try:
                    legend_list = json.loads(legend_labels)
                except json.JSONDecodeError as e:
                    return {
                        "status": "error",
                        "content": [
                            {
                                "text": f"Invalid JSON in legend_labels parameter: {str(e)}. "
                                "Expected a JSON array of strings, e.g. "
                                '["Series A", "Series B"].'
                            }
                        ],
                    }

                if (
                    not isinstance(legend_list, list)
                    or not legend_list
                    or not all(isinstance(l, str) and l.strip() for l in legend_list)
                ):
                    return {
                        "status": "error",
                        "content": [
                            {
                                "text": "legend_labels must be a non-empty JSON array of non-empty strings."
                            }
                        ],
                    }

            # Lazy import matplotlib — only loaded when a chart is actually requested
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            # Default color palette
            default_colors = [
                "#4ECDC4",
                "#FF6B6B",
                "#45B7D1",
                "#96CEB4",
                "#FFEAA7",
                "#DDA0DD",
                "#98D8C8",
                "#F7DC6F",
                "#BB8FCE",
                "#85C1E9",
            ]

            def _get_colors(n):
                """Return n colors from provided list or defaults."""
                palette = color_list if color_list else default_colors
                if not palette:
                    palette = default_colors
                return [palette[i % len(palette)] for i in range(n)]

            # --- Dynamic figsize based on data volume ---
            BASE_W, BASE_H = 10, 6
            MIN_W, MIN_H = 10, 6
            MAX_W, MAX_H = 40, 20
            INCH_PER_LABEL = 0.5
            INCH_PER_ROW = 0.35

            def _compute_figsize(ctype, cdata):
                """Return (width, height) tuple scaled to data volume."""
                w, h = BASE_W, BASE_H

                if ctype in ("bar", "line"):
                    n_labels = len(cdata.get("labels", []))
                    datasets = cdata.get("datasets", [])
                    n_datasets = max(len(datasets), 1)
                    w = max(
                        BASE_W, n_labels * INCH_PER_LABEL * max(1, n_datasets * 0.6)
                    )
                    h = BASE_H + (1.5 if n_datasets > 3 else 0)
                elif ctype == "heatmap":
                    n_x = len(cdata.get("x_labels", []))
                    n_y = len(cdata.get("y_labels", []))
                    w = max(BASE_W, n_x * INCH_PER_LABEL)
                    h = max(BASE_H, n_y * INCH_PER_ROW + 2)
                elif ctype == "table":
                    n_rows = len(cdata.get("rows", []))
                    n_cols = len(cdata.get("headers", []))
                    w = max(BASE_W, n_cols * 1.8)
                    h = max(BASE_H, n_rows * INCH_PER_ROW + 2)
                elif ctype == "pie":
                    n_labels = len(cdata.get("labels", []))
                    if n_labels > 6:
                        size = min(BASE_W + (n_labels - 6) * 0.3, 14)
                        w = h = max(BASE_W, size)

                return min(max(w, MIN_W), MAX_W), min(max(h, MIN_H), MAX_H)

            MAX_LABEL_LEN = 18

            def _truncate_labels(labels, max_len=MAX_LABEL_LEN):
                """Truncate long labels with ellipsis."""
                result = []
                for lbl in labels:
                    s = str(lbl)
                    result.append(
                        (s[: max_len - 1] + "\u2026") if len(s) > max_len else s
                    )
                return result

            def _tick_style(n):
                """Return (rotation, ha, fontsize) for n tick labels."""
                rotation = 90 if n > 15 else (45 if n > 6 else 0)
                ha = "right" if rotation else "center"
                fontsize = max(7, 10 - n // 8)
                return rotation, ha, fontsize

            def _render_bar(fig, ax, chart_data):
                labels = chart_data["labels"]
                datasets = chart_data["datasets"]

                if sort_descending and len(datasets) == 1:
                    paired = sorted(
                        zip(labels, datasets[0]["values"]),
                        key=lambda x: x[1],
                        reverse=True,
                    )
                    labels = [p[0] for p in paired]
                    datasets[0]["values"] = [p[1] for p in paired]

                import numpy as np

                x = np.arange(len(labels))
                n_datasets = len(datasets)
                bar_width = 0.8 / n_datasets if not stacked else 0.8
                bar_colors = _get_colors(n_datasets)

                bottom = np.zeros(len(labels)) if stacked else None

                for i, ds in enumerate(datasets):
                    offset = (
                        (i - n_datasets / 2 + 0.5) * bar_width if not stacked else 0
                    )
                    label = (
                        legend_list[i]
                        if legend_list and i < len(legend_list)
                        else ds.get("name", f"Series {i+1}")
                    )
                    if stacked:
                        ax.bar(
                            x,
                            ds["values"],
                            bar_width,
                            bottom=bottom,
                            label=label,
                            color=bar_colors[i],
                        )
                        bottom += np.array(ds["values"])
                    else:
                        ax.bar(
                            x + offset,
                            ds["values"],
                            bar_width,
                            label=label,
                            color=bar_colors[i],
                        )

                rotation, ha, fontsize = _tick_style(len(labels))
                ax.set_xticks(x)
                ax.set_xticklabels(
                    _truncate_labels(labels),
                    rotation=rotation,
                    ha=ha,
                    fontsize=fontsize,
                )
                if n_datasets > 1 or legend_list:
                    ax.legend()

            def _render_line(fig, ax, chart_data):
                labels = chart_data["labels"]
                datasets = chart_data["datasets"]
                line_colors = _get_colors(len(datasets))

                for i, ds in enumerate(datasets):
                    label = (
                        legend_list[i]
                        if legend_list and i < len(legend_list)
                        else ds.get("name", f"Series {i+1}")
                    )
                    ax.plot(
                        labels,
                        ds["values"],
                        marker="o",
                        label=label,
                        color=line_colors[i],
                        linewidth=2,
                    )

                rotation, ha, fontsize = _tick_style(len(labels))
                ax.set_xticks(range(len(labels)))
                ax.set_xticklabels(
                    _truncate_labels(labels),
                    rotation=rotation,
                    ha=ha,
                    fontsize=fontsize,
                )
                if len(datasets) > 1 or legend_list:
                    ax.legend()
                ax.grid(True, alpha=0.3)

            def _render_pie(fig, ax, chart_data):
                labels = chart_data["labels"]
                values = chart_data["values"]

                if sort_descending:
                    paired = sorted(
                        zip(labels, values), key=lambda x: x[1], reverse=True
                    )
                    labels = [p[0] for p in paired]
                    values = [p[1] for p in paired]

                pie_colors = _get_colors(len(labels))
                LEGEND_THRESHOLD = 10

                if len(labels) > LEGEND_THRESHOLD:
                    wedges, texts, autotexts = ax.pie(
                        values,
                        colors=pie_colors,
                        autopct="%1.1f%%",
                        startangle=90,
                        pctdistance=0.85,
                    )
                    ax.legend(
                        wedges,
                        _truncate_labels(labels),
                        loc="center left",
                        bbox_to_anchor=(1, 0, 0.5, 1),
                        fontsize=8,
                    )
                else:
                    wedges, texts, autotexts = ax.pie(
                        values,
                        labels=labels,
                        colors=pie_colors,
                        autopct="%1.1f%%",
                        startangle=90,
                        pctdistance=0.85,
                    )
                for text in autotexts:
                    text.set_fontsize(9)
                ax.axis("equal")

            def _render_scatter(fig, ax, chart_data):
                datasets = chart_data["datasets"]
                scatter_colors = _get_colors(len(datasets))

                for i, ds in enumerate(datasets):
                    label = (
                        legend_list[i]
                        if legend_list and i < len(legend_list)
                        else ds.get("name", f"Series {i+1}")
                    )
                    ax.scatter(
                        ds["x"],
                        ds["y"],
                        label=label,
                        color=scatter_colors[i],
                        alpha=0.7,
                        s=60,
                    )

                if len(datasets) > 1 or legend_list:
                    ax.legend()
                ax.grid(True, alpha=0.3)

            def _render_heatmap(fig, ax, chart_data):
                import numpy as np

                x_labels = chart_data["x_labels"]
                y_labels = chart_data["y_labels"]
                values = np.array(chart_data["values"])

                im = ax.imshow(values, cmap="YlOrRd", aspect="auto")
                fig.colorbar(im, ax=ax)

                ax.set_xticks(range(len(x_labels)))
                ax.set_xticklabels(
                    _truncate_labels(x_labels),
                    rotation=_tick_style(len(x_labels))[0] or 45,
                    ha="right",
                    fontsize=_tick_style(len(x_labels))[2],
                )
                ax.set_yticks(range(len(y_labels)))
                ax.set_yticklabels(
                    _truncate_labels(y_labels),
                    fontsize=_tick_style(len(y_labels))[2],
                )

                # Annotate cells with values
                for i in range(len(y_labels)):
                    for j in range(len(x_labels)):
                        val = values[i][j]
                        text_color = (
                            "white"
                            if val > (values.max() + values.min()) / 2
                            else "black"
                        )
                        ax.text(
                            j,
                            i,
                            str(val),
                            ha="center",
                            va="center",
                            color=text_color,
                            fontsize=9,
                        )

            def _render_table(fig, ax, chart_data):
                headers = chart_data["headers"]
                rows = chart_data["rows"]

                ax.axis("off")
                table = ax.table(
                    cellText=rows,
                    colLabels=headers,
                    cellLoc="center",
                    loc="center",
                )
                table.auto_set_font_size(False)
                table.set_fontsize(10)
                table.scale(1.2, 1.5)

                # Style header row
                for j in range(len(headers)):
                    cell = table[0, j]
                    cell.set_facecolor("#4ECDC4")
                    cell.set_text_props(color="white", fontweight="bold")

                # Alternate row colors
                for i in range(len(rows)):
                    for j in range(len(headers)):
                        cell = table[i + 1, j]
                        cell.set_facecolor("#F8F9FA" if i % 2 == 0 else "#FFFFFF")

            # Render the chart
            renderers = {
                "bar": _render_bar,
                "line": _render_line,
                "pie": _render_pie,
                "scatter": _render_scatter,
                "heatmap": _render_heatmap,
                "table": _render_table,
            }

            fig = None
            try:
                fig_w, fig_h = _compute_figsize(chart_type, chart_data)
                fig, ax = plt.subplots(figsize=(fig_w, fig_h))
                fig.patch.set_facecolor("white")

                renderers[chart_type](fig, ax, chart_data)

                ax.set_title(title, fontsize=14, fontweight="bold", pad=15)
                if x_label and chart_type not in ("pie", "table"):
                    ax.set_xlabel(x_label)
                if y_label and chart_type not in ("pie", "table"):
                    ax.set_ylabel(y_label)

                plt.tight_layout()

                # Render to PNG bytes
                buf = io.BytesIO()
                dpi = 100 if fig_w > 20 else 150
                fig.savefig(
                    buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white"
                )
                buf.seek(0)
                png_bytes = buf.getvalue()
            finally:
                if fig is not None:
                    plt.close(fig)

            # Ensure filename ends with .png
            if not filename.lower().endswith(".png"):
                filename = filename + ".png"

            # Append to shared attachments list (bytes content)
            attachments_list.append(
                {
                    "filename": filename,
                    "content": png_bytes,
                    "title": title,
                }
            )

            return {
                "status": "success",
                "content": [
                    {
                        "text": f"Chart '{title}' generated successfully as '{filename}' and will be uploaded to the thread."
                    }
                ],
            }

        except KeyError as e:
            return {
                "status": "error",
                "content": [
                    {
                        "text": f"Missing required field in data: {str(e)}. Check the data format for chart_type '{chart_type}'."
                    }
                ],
            }
        except Exception as e:
            return {
                "status": "error",
                "content": [{"text": f"Failed to generate chart: {str(e)}"}],
            }

    return create_chart
