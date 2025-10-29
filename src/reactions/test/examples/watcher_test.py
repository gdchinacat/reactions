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


from unittest import main, TestCase

from ... import (ExecutorFieldManager, Field, And, Not, FieldWatcher,
                 FieldChange)


class Watched(ExecutorFieldManager):
    '''
    Example class that has a field to be watched by Watcher. Class counts the
    stop_predicate value then stops.
    '''
    field = Field['Watched', int](-1)
    '''state field initialized to -1'''

    stop_predicate = field >= 5
    '''the condition at which to stop'''

    stop_predicate(ExecutorFieldManager.astop)
    '''call FieldManager.astop when the stop predicate becomes True'''

    def _start(self) -> None:
        '''start the count by changing field to 0'''
        self.field = 0

    @ And(field != -1,
          Not(stop_predicate))
    async def increment(self, change: FieldChange[Watched, int]) -> None:
        '''increment the field value until the stop predicate is true'''
        self.field += 1


class Watcher(FieldWatcher[Watched]):
    '''FieldWatcher that watches Watched field changes.'''

    last_value: int|None = None
    '''attribute that tracks the watched field value'''

    @ Watched.field != -1
    @ FieldWatcher.manage
    async def watch_watched_field(self,
                                  watched: Watched,
                                  change: FieldChange[Watched, int]) -> None:
        # for test, just make sure the old and new values are correct
        if self.last_value is not None:
            assert self.last_value == change.old
            assert change.new == self.last_value + 1
        self.last_value = change.new


class WatcherTest(TestCase):
    '''examples showing how one class can watch the fields on another'''
    
    def test_watcher_shared_executor(self)->None:
        '''Watcher using the same executor (the default).'''
        watched = Watched()
        watcher = Watcher(watched)

        watched.run()
        self.assertEqual(watched.field, watcher.last_value)


if __name__ == '__main__':
    main()