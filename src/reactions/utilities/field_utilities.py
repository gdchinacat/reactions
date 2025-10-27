# Copyright (C) 2025 Anthony (Lonnie) Hutchinson <chinacat@chinacat.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''
Utilifies related to Fields.
'''
from typing import TypeVar


from ..field import Field, FieldWatcher


def adjust_while[Tw, T](
        field: Field[T, bool], attr: str, adj: float,
        namespace: dict[str, object],
        watcher: bool = False) -> None:
    '''
    Make it so the value in attr is adjusted by adj amount while field
    is true. This works by creating reactions in the namespace to increment
    the value in attr when the field becomes true and decrement it when it
    becomes false.
    field: field that determines when the value is adjusted
    attr: the attribute on self that will be adjusted
    adj: the amount to adjust attr by when field is true
    namespace: the class namespace to add the reactions to (required so
               FieldWatcher can manage them. The name of the reaction in
               the namespace is __fieldname_action.
    watcher: is the reaction being created on a watcher? (default=False)
    '''
    for (v, _adj, action) in ((True, adj, 'pressed'),
                              (False, -adj, 'released')):
        def create_reaction(v: bool, _adj: float, action: str) -> None:
            '''
            create a reaction in the namespace that adjusts the value
            in attr by _adj amount when field changes to v.
            '''
            async def reaction(self: Tw, *_: object) -> None:
                setattr(self, attr, getattr(self, attr) + _adj)
            _reaction = FieldWatcher.manage(reaction) if watcher else reaction
            namespace[f'_{field.attr}_{action}'] = (field == v)(_reaction)
        create_reaction(v, _adj, action)
