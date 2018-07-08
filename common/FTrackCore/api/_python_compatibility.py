# :coding: utf-8
# :copyright: Copyright (c) 2014 ftrack

'''Compatibility implementations for Python.

Most are direct copies from later versions of Python.

'''

import inspect
import copy
import types
import collections

# Add helper to convert unicode keywords to strings for early Python 2.6
# versions. See http://bugs.python.org/issue2646
UNICODE_KEYWORDS_SUPPORTED = True


def ensure_compatible_keywords(mapping):
    '''Convert unicode keywords in *mapping* to strings if required.

    *mapping* is altered in place.

    '''
    if UNICODE_KEYWORDS_SUPPORTED:
        return

    if not isinstance(mapping, collections.MutableMapping):
        return

    for key, value in mapping.items():
        del mapping[key]
        mapping[str(key)] = value


def _test_unicode_keywords(**kw):
    pass


try:
    _test_unicode_keywords(**{u'unicode_key': True})
except TypeError as error:
    if 'keywords must be strings' in str(error):
        UNICODE_KEYWORDS_SUPPORTED = False


# Support deepcopying instance methods. See http://bugs.python.org/issue1515.
try:
    copy._deepcopy_dispatch[types.MethodType]
except KeyError:  # pragma: no cover

    def _deepcopy_method(x, memo):
        return type(x)(x.im_func, copy.deepcopy(x.im_self, memo), x.im_class)

    copy._deepcopy_dispatch[types.MethodType] = _deepcopy_method


# inspect.getcallargs for Python < 2.7
try:
    inspect.getcallargs
except AttributeError:
    def getcallargs(func, *positional, **named):
        """Get the mapping of arguments to values.

        A dict is returned, with keys the function argument names (including the
        names of the * and ** arguments, if any), and values the respective bound
        values from 'positional' and 'named'."""
        args, varargs, varkw, defaults = inspect.getargspec(func)
        f_name = func.__name__
        arg2value = {}

        # The following closures are basically because of tuple parameter unpacking.
        assigned_tuple_params = []
        def assign(arg, value):
            if isinstance(arg, str):
                arg2value[arg] = value
            else:
                assigned_tuple_params.append(arg)
                value = iter(value)
                for i, subarg in enumerate(arg):
                    try:
                        subvalue = next(value)
                    except StopIteration:
                        raise ValueError('need more than %d %s to unpack' %
                                         (i, 'values' if i > 1 else 'value'))
                    assign(subarg,subvalue)
                try:
                    next(value)
                except StopIteration:
                    pass
                else:
                    raise ValueError('too many values to unpack')
        def is_assigned(arg):
            if isinstance(arg,str):
                return arg in arg2value
            return arg in assigned_tuple_params
        if inspect.ismethod(func) and func.im_self is not None:
            # implicit 'self' (or 'cls' for classmethods) argument
            positional = (func.im_self,) + positional
        num_pos = len(positional)
        num_total = num_pos + len(named)
        num_args = len(args)
        num_defaults = len(defaults) if defaults else 0
        for arg, value in zip(args, positional):
            assign(arg, value)
        if varargs:
            if num_pos > num_args:
                assign(varargs, positional[-(num_pos-num_args):])
            else:
                assign(varargs, ())
        elif 0 < num_args < num_pos:
            raise TypeError('%s() takes %s %d %s (%d given)' % (
                f_name, 'at most' if defaults else 'exactly', num_args,
                'arguments' if num_args > 1 else 'argument', num_total))
        elif num_args == 0 and num_total:
            if varkw:
                if num_pos:
                    # XXX: We should use num_pos, but Python also uses num_total:
                    raise TypeError('%s() takes exactly 0 arguments '
                                    '(%d given)' % (f_name, num_total))
            else:
                raise TypeError('%s() takes no arguments (%d given)' %
                                (f_name, num_total))
        for arg in args:
            if isinstance(arg, str) and arg in named:
                if is_assigned(arg):
                    raise TypeError("%s() got multiple values for keyword "
                                    "argument '%s'" % (f_name, arg))
                else:
                    assign(arg, named.pop(arg))
        if defaults:    # fill in any missing values with the defaults
            for arg, value in zip(args[-num_defaults:], defaults):
                if not is_assigned(arg):
                    assign(arg, value)
        if varkw:
            assign(varkw, named)
        elif named:
            unexpected = next(iter(named))
            if isinstance(unexpected, unicode):
                unexpected = unexpected.encode(sys.getdefaultencoding(), 'replace')
            raise TypeError("%s() got an unexpected keyword argument '%s'" %
                            (f_name, unexpected))
        unassigned = num_args - len([arg for arg in args if is_assigned(arg)])
        if unassigned:
            num_required = num_args - num_defaults
            raise TypeError('%s() takes %s %d %s (%d given)' % (
                f_name, 'at least' if defaults else 'exactly', num_required,
                'arguments' if num_required > 1 else 'argument', num_total))
        return arg2value


    inspect.getcallargs = getcallargs