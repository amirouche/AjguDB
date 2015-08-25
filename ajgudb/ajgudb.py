# AjuDB - leveldb powered graph database
# Copyright (C) 2015 Amirouche Boubekki <amirouche@hypermove.net>

# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.

# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA  02110-1301  USA
from utils import AjguDBException

from leveldb import LevelDBStorage

from gremlin import GremlinResult
from gremlin import GremlinIterator


class Base(dict):

    def delete(self):
        self._graphdb._tuples.delete(self.uid)

    def __eq__(self, other):
        if isinstance(other, Base):
            return self.uid == other.uid
        return False

    def __repr__(self):
        return '<%s %s>' % (type(self).__name__, self.uid)

    def __nonzero__(self):
        return True


class Vertex(Base):

    def __init__(self, graphdb, uid, properties):
        self._graphdb = graphdb
        self.uid = uid
        super(Vertex, self).__init__(properties)

    def _iter_edges(self, _vertex):
        def edges():
            key = '_meta_%s' % _vertex
            records = self._graphdb._tuples.query(key, self.uid)
            for _, _, uid in records:
                yield GremlinResult(uid, None, None)

        return GremlinIterator(self._graphdb, edges())

    def incomings(self):
        return self._iter_edges('end')

    def outgoings(self):
        return self._iter_edges('start')

    def save(self):
        self._graphdb._tuples.update(
            self.uid,
            _meta_type='vertex',
            **self
        )
        return self

    def link(self, end, **properties):
        properties['_meta_start'] = self.uid
        properties['_meta_end'] = end.uid
        uid = self._graphdb._uid()
        self._graphdb._tuples.add(uid, _meta_type='edge', **properties)
        return Edge(self._graphdb, uid, properties)


class Edge(Base):

    def __init__(self, graphdb, uid, properties):
        self._graphdb = graphdb
        self.uid = uid
        self._start = properties.pop('_meta_start')
        self._end = properties.pop('_meta_end')
        super(Edge, self).__init__(properties)

    def start(self):
        properties = self._graphdb._tuples.get(self._start)
        return Vertex(self._graphdb, self._start, properties)

    def end(self):
        properties = self._graphdb._tuples.get(self._end)
        return Vertex(self._graphdb, self._end, properties)

    def save(self):
        self._graphdb._tuples.update(
            self.uid,
            _meta_type='edge',
            _meta_start=self._start,
            _meta_end=self._end,
            **self
        )
        return self

    def delete(self):
        self._graphdb._tuples.delete(self.uid)


class AjguDB(object):

    def __init__(self, path):
        self._tuples = LevelDBStorage(path)

    def close(self):
        self._tuples.close()

    def _uid(self):
        try:
            counter = self._tuples.get(0)['counter']
        except KeyError:
            self._tuples.add(0, counter=1)
            return 1
        else:
            counter += 1
            self._tuples.update(0, counter=counter)
            return counter

    def get(self, uid):
        properties = self._tuples.get(uid)
        if properties:
            meta_type = properties.pop('_meta_type')
            if meta_type == 'vertex':
                return Vertex(self, uid, properties)
            else:
                return Edge(self, uid, properties)
        else:
            raise AjguDBException('%s not found' % uid)

    def vertex(self, **properties):
        uid = self._uid()
        self._tuples.add(uid, _meta_type='vertex', **properties)
        return Vertex(self, uid, properties)

    def get_or_create(self, **properties):
        vertex = self.select(**properties).one(None)
        if vertex:
            return vertex
        else:
            return self.vertex(**properties)

    def select(self, **properties):
        def iterator():
            key, value = properties.items()[0]
            for _, _, uid in self._tuples.query(key, value):
                yield GremlinResult(uid, None, None)

        return GremlinIterator(self, iterator()).select(**properties)

    def vertices(self):
        def iterator():
            for _, _, uid in self._tuples.query('_meta_type', 'vertex'):
                yield GremlinResult(uid, None, None)

        return GremlinIterator(self, iterator())

    def edges(self):
        def iterator():
            for _, _, uid in self._tuples.query('_meta_type', 'edge'):
                yield GremlinResult(uid, None, None)

        return GremlinIterator(self, iterator())