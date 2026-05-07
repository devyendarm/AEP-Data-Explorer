from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PySide6.QtCore import QRegularExpression

class SqlHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)

        self.highlighting_rules = []

        # Keywords
        keywords = [
            "SELECT", "FROM", "WHERE", "INSERT", "INTO", "VALUES", "UPDATE", "DELETE",
            "CREATE", "TABLE", "DROP", "ALTER", "GRANT", "REVOKE", "JOIN", "LEFT",
            "RIGHT", "INNER", "OUTER", "ON", "AND", "OR", "NOT", "NULL", "IS", "IN",
            "BETWEEN", "LIKE", "LIMIT", "OFFSET", "ORDER", "BY", "GROUP", "HAVING",
            "AS", "CASE", "WHEN", "THEN", "ELSE", "END", "DISTINCT", "UNION", "ALL",
            "CAST", "CONVERT", "TRUE", "FALSE"
        ]
        
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569cd6")) # VS Code Blue
        keyword_format.setFontWeight(QFont.Bold)

        for word in keywords:
            pattern = QRegularExpression(f"\\b{word}\\b", QRegularExpression.CaseInsensitiveOption)
            self.highlighting_rules.append((pattern, keyword_format))

        # Strings ('value')
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#ce9178")) # VS Code Orange/Red
        self.highlighting_rules.append((QRegularExpression("'.*?'"), string_format))

        # Numbers
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#b5cea8")) # VS Code Light Green
        self.highlighting_rules.append((QRegularExpression("\\b\\d+\\b"), number_format))

        # Comments (-- comment)
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6a9955")) # VS Code Green
        self.highlighting_rules.append((QRegularExpression("--[^\n]*"), comment_format))
        
        # Comments (/* ... */) - simplified, only single line supported well with regex here
        self.highlighting_rules.append((QRegularExpression("/\\*.*\\*/"), comment_format))

    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)
