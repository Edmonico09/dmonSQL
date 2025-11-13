# ============================================================================
# dmonSQL/query/parser.py
# ============================================================================
"""Parseur SQL pour dmonSQL"""

import re
from typing import Dict, List, Tuple, Optional


class QueryParser:
    """Parseur SQL basique"""
    
    @staticmethod
    # def parse_create_table(sql: str) -> Tuple[str, List]:
    #     """Parse CREATE TABLE"""
    #     from dmonSQL.core.column import Column
        
    #     match = re.match(r'CREATE\s+TABLE\s+(\w+)\s*\((.*)\)', sql, re.IGNORECASE | re.DOTALL)
    #     if not match:
    #         raise ValueError("Invalid CREATE TABLE syntax")
        
    #     table_name = match.group(1)
    #     columns_def = match.group(2)
        
    #     columns = []
    #     for col_def in columns_def.split(','):
    #         col_def = col_def.strip()
    #         parts = col_def.split()
            
    #         if len(parts) < 2:
    #             continue
            
    #         col_name = parts[0]
    #         col_type = parts[1].upper()
            
    #         length = None
    #         if '(' in col_type:
    #             col_type, length_str = col_type.split('(')
    #             length = int(length_str.rstrip(')'))
            
    #         nullable = 'NOT NULL' not in col_def.upper()
    #         primary_key = 'PRIMARY KEY' in col_def.upper()
    #         auto_increment = 'AUTO_INCREMENT' in col_def.upper()
    #         unique = 'UNIQUE' in col_def.upper()
            
    #         columns.append(Column(col_name, col_type, length, nullable, 
    #                             primary_key, auto_increment, unique))
        
    #     return table_name, columns
    
    def parse_create_table(sql: str):
        """Parse CREATE TABLE avec support des FOREIGN KEY"""
        
        # Pattern amélioré qui exclut FOREIGN KEY de la liste des colonnes
        pattern = r'CREATE\s+TABLE\s+(\w+)\s*\((.*)\)'
        match = re.match(pattern, sql, re.IGNORECASE | re.DOTALL)
        
        if not match:
            raise ValueError("Invalid CREATE TABLE syntax")
        
        table_name = match.group(1)
        content = match.group(2).strip()
        
        columns = []
        foreign_keys = []
        
        # Séparer les définitions (colonnes et contraintes)
        parts = []
        paren_depth = 0
        current_part = ""
        
        for char in content:
            if char == '(':
                paren_depth += 1
            elif char == ')':
                paren_depth -= 1
            elif char == ',' and paren_depth == 0:
                parts.append(current_part.strip())
                current_part = ""
                continue
            current_part += char
        
        if current_part.strip():
            parts.append(current_part.strip())
        
        # Parser chaque partie
        for part in parts:
            part_upper = part.upper().strip()
            
            # Vérifier si c'est une contrainte FOREIGN KEY
            if part_upper.startswith('FOREIGN KEY'):
                # Parser: FOREIGN KEY (conv_id) REFERENCES conversation(id)
                fk_pattern = r'FOREIGN\s+KEY\s*\((\w+)\)\s*REFERENCES\s+(\w+)\s*\((\w+)\)(?:\s+ON\s+DELETE\s+(\w+))?(?:\s+ON\s+UPDATE\s+(\w+))?'
                fk_match = re.match(fk_pattern, part, re.IGNORECASE)
                
                if fk_match:
                    fk = {
                        'column': fk_match.group(1),
                        'ref_table': fk_match.group(2),
                        'ref_column': fk_match.group(3),
                        'on_delete': fk_match.group(4) or 'RESTRICT',
                        'on_update': fk_match.group(5) or 'RESTRICT'
                    }
                    foreign_keys.append(fk)
                    continue
            
            # Sinon, c'est une définition de colonne
            # Parser: nom TYPE [PRIMARY KEY] [AUTO_INCREMENT] [NOT NULL] etc.
            col_pattern = r'(\w+)\s+(\w+)(?:\((\d+)\))?((?:\s+(?:PRIMARY\s+KEY|AUTO_INCREMENT|NOT\s+NULL|UNIQUE|DEFAULT\s+\S+))*)'
            col_match = re.match(col_pattern, part, re.IGNORECASE)
            
            if col_match:
                col_name = col_match.group(1)
                col_type = col_match.group(2).upper()
                col_length = int(col_match.group(3)) if col_match.group(3) else None
                modifiers = col_match.group(4).upper() if col_match.group(4) else ""
                
                from dmonSQL.core.column import Column
                
                column = Column(
                    name=col_name,
                    dtype=col_type,
                    length=col_length,
                    nullable='NOT NULL' not in modifiers,
                    primary_key='PRIMARY KEY' in modifiers,
                    auto_increment='AUTO_INCREMENT' in modifiers,
                    unique='UNIQUE' in modifiers
                )
                columns.append(column)
        
        return table_name, columns, foreign_keys

    @staticmethod
    def parse_select(sql: str) -> Dict:
        """Parse SELECT"""
        match = re.match(r'SELECT\s+(.*?)\s+FROM\s+(\w+)(?:\s+WHERE\s+(.*))?', 
                        sql, re.IGNORECASE)
        if not match:
            raise ValueError("Invalid SELECT syntax")
        
        return {
            'type': 'SELECT',
            'columns': match.group(1).strip(),
            'table': match.group(2),
            'where': match.group(3)
        }

