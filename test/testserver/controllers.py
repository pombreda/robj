#
# Copyright (c) 2010 rPath, Inc.
#
# This program is distributed under the terms of the MIT License as found 
# in a file called LICENSE. If it is not present, the license
# is always available at http://www.opensource.org/licenses/mit-license.php.
#
# This program is distributed in the hope that it will be useful, but
# without any waranty; without even the implied warranty of merchantability
# or fitness for a particular purpose. See the MIT License for full details.
#

from SimpleHTTPServer import SimpleHTTPRequestHandler

from xobj import xobj

from testserver import models
from testserver.modelmgr import AttrDict

class Response(object):
    def __init__(self, doc=None, code=200, model=None, tag=None):
        self._doc = doc
        self.code = code
        self._model = model
        self._tag = tag

        assert self.code in SimpleHTTPRequestHandler.responses

    @property
    def message(self):
        if self._doc is not None:
            return self._doc
        elif self._model is not None:
            if self._tag is not None:
                tag = self._tag
            else:
                tag = self._model.__tag__
            return xobj.toxml(self._model, tag)
        else:
            return ''


class ControllerMgr(dict):
    _CONTROLLER = '%CONTROLLER%'

    @staticmethod
    def _splitPath(path):
        return path.split('/')

    @staticmethod
    def _isVariable(element):
        if element.startswith('{') and element.endswith('}'):
            return element.strip('}').lstrip('{')
        return False

    def register(self, cls):
        cur = self
        for element in self._splitPath(cls.__uri__):
            if element not in cur:
                cur[element] = {}
            cur = cur[element]

        cur[self._CONTROLLER] = cls

    def get(self, uri):
        cur = self
        vars = AttrDict()
        uri = uri.rstrip('/')
        for element in self._splitPath(uri):
            if element in cur:
                cur = cur[element]
                continue

            elif element.isdigit():
                for key, val in cur.iteritems():
                    var = self._isVariable(key)
                    if var:
                        cur = val
                        vars[var] = int(element)
                        break
                else:
                    return NotFoundController, vars
                    raise RuntimeError, 'invalid path variable: %s' % element

            else:
                return NotFoundController, vars
                raise RuntimeError, 'unknown element in path: %s' % element

        if self._CONTROLLER not in cur:
            return NotFoundController, vars

        cls = cur[self._CONTROLLER]
        return cls, vars

controllers = ControllerMgr()


class AbstractController(object):
    __uri__ = None

    def __init__(self, data, handler, pathVars=None):
        self.data = data
        self.handler = handler

        self.pathVars = AttrDict()
        if pathVars:
            self.pathVars = pathVars

    def do_GET(self): return Response(code=501)
    def do_PUT(self): return Response(code=501)
    def do_POST(self): return Response(code=501)
    def do_DELETE(self): return Response(code=501)

    def _getinput(self):
        length = int(self.handler.headers.getheader('content-length'))
        return self.handler.rfile.read(length)


class AbstractCollectionController(AbstractController):
    def do_POST(self):
        return self.do_PUT()


class NotFoundController(AbstractController):
    def notFound(self):
        return Response(code=404)
    do_GET = do_PUT = do_POST = do_DELETE = notFound


class Api(AbstractController):
    __uri__ = '/api'

    def do_GET(self):
        api = models.Api()
        api.version = '1.0'
        api.employees = models.EmployeesRef()
        api.employees.href = Employees.__uri__
        api.products = models.ProductsRef()
        api.products.href = Products.__uri__

        return Response(code=200, model=api)
controllers.register(Api)


class Employee(AbstractController):
    __uri__ = '/api/employees/{idx}'

    def do_GET(self):
        idx = self.pathVars.idx
        model = self.data.employees.get(idx, None)
        if not model:
            return Response(code=404)
        else:
            return Response(code=200, model=model)

    def do_PUT(self):
        idx = self.pathVars.idx
        if idx not in self.data.employees:
            return Response(code=404)
        else:
            xml = self._getinput()
            model = self.data.employees.update(idx, xml)
            return Response(code=200, model=model)

    def do_DELETE(self):
        idx = self.pathVars.idx
        if idx not in self.data.employees:
            return Response(code=404)
        else:
            self.data.employees.delete(idx)
            return Response(code=200)
controllers.register(Employee)


class Product(AbstractController):
    __uri__ = '/api/products/{idx}'

    def do_GET(self):
        idx = self.pathVars.idx
        model = self.data.products.get(idx, None)
        if not model:
            return Response(code=404)
        else:
            return Response(code=200, model=model)

    def do_PUT(self):
        idx = self.pathVars.idx
        if idx not in self.data.products:
            return Response(code=404)
        else:
            xml = self._getinput()
            model = self.data.product.update(idx, xml)
            return Response(code=200, model=model)

    def do_DELETE(self):
        idx = self.pathVars.idx
        if idx not in self.data.products:
            return Response(code=404)
        else:
            self.data.products.delete(idx)
            return Response(code=200)
controllers.register(Product)


class Employees(AbstractCollectionController):
    __uri__ = '/api/employees'

    def do_GET(self):
        employees = [ x for x in sorted(self.data.employees.itervalues()) ]
        model = models.Employees()
        model.employees = employees
        model.id = self.handler.path

        return Response(code=200, model=model)

    def do_PUT(self):
        xml = self._getinput()
        model = self.data.employees.create(xml, self.handler.path)
        return Response(code=201, model=model)
controllers.register(Employees)


class ProductEmployees(Employees):
    __uri__ = '/api/products/{idx}/employees'

    def do_GET(self):
        idx = self.pathVars.idx
        if not self.data.products.get(idx, None):
            return Response(code=404)

        employees = [ self.data.employees[x]
            for x in sorted(self.data.products.employeeRefs.get(idx))
                if x in self.data.employees ]

        model = models.Employees()
        model.employees = employees
        model.id = self.handler.path

        return Response(code=200, model=model)

    def do_PUT(self):
        idx = self.pathVars.idx
        if not self.data.products.get(idx, None):
            return Response(code=404)

        xml = self._getinput()
        model = self.data.employees.create(xml, Employees.__uri__)
        self.data.products.employeeRefs[idx].append(model.employeeid)
        self.data.employees.productRefs[model.employeeid].append(idx)

        return Response(code=200, model=model)
controllers.register(ProductEmployees)


class Products(AbstractCollectionController):
    __uri__ = '/api/products'

    def do_GET(self):
        products = [ x for x in sorted(self.data.products.itervalues()) ]
        model = models.Products()
        model.products = products
        model.id = self.handler.path

        return Response(code=200, model=model)

    def do_PUT(self):
        xml = self._getinput()
        model = self.data.products.create(xml, self.handler.path)
        return Response(code=201, model=model)
controllers.register(Products)


class EmployeeProducts(Products):
    __uri__ = '/api/employees/{idx}/products'

    def do_GET(self):
        idx = self.pathVars.idx
        if not self.data.employees.get(idx, None):
            return Response(code=404)

        products = [ self.data.products[x]
            for x in sorted(self.data.employees.productRefs.get(idx))
                if x in self.data.products ]

        model = models.Products()
        model.products = products
        model.id = self.handler.path

        return Response(code=200, model=model)

    def do_PUT(self):
        idx = self.pathVars.idx
        if not self.data.products.get(idx, None):
            return Response(code=404)

        xml = self._getinput()
        model = self.data.products.create(xml, Products.__uri__)
        self.data.employees.productRefs[idx].append(model.productid)
        self.data.products.employeeRefs[model.productid].append(idx)

        return Response(code=200, model=model)
controllers.register(EmployeeProducts)