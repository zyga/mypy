"""Test cases for mypy types and type operations."""

from typing import List

from mypy.myunit import (
    Suite, assert_equal, assert_true, assert_false, run_test
)
from mypy.erasetype import erase_type
from mypy.expandtype import expand_type
from mypy.join import join_types
from mypy.meet import meet_types
from mypy.types import (
    UnboundType, AnyType, Void, Callable, TupleType, TypeVarDef, Type,
    Instance, NoneTyp, ErrorType
)
from mypy.nodes import ARG_POS, ARG_OPT, ARG_STAR
from mypy.replacetvars import replace_type_vars
from mypy.subtypes import is_subtype, is_more_precise, is_proper_subtype
from mypy.typefixture import TypeFixture, InterfaceTypeFixture


class TypesSuite(Suite):
    def __init__(self):
        super().__init__()
        self.x = UnboundType('X')  # Helpers
        self.y = UnboundType('Y')

    def test_any(self):
        assert_equal(str(AnyType()), 'Any')

    def test_simple_unbound_type(self):
        u = UnboundType('Foo')
        assert_equal(str(u), 'Foo?')

    def test_generic_unbound_type(self):
        u = UnboundType('Foo', [UnboundType('T'), AnyType()])
        assert_equal(str(u), 'Foo?[T?, Any]')

    def test_void_type(self):
        assert_equal(str(Void(None)), 'void')

    def test_callable_type(self):
        c = Callable([self.x, self.y],
                     [ARG_POS, ARG_POS],
                     [None, None],
                     AnyType(), False)
        assert_equal(str(c), 'def (X?, Y?) -> Any')

        c2 = Callable([], [], [], Void(None), False)
        assert_equal(str(c2), 'def ()')

    def test_callable_type_with_default_args(self):
        c = Callable([self.x, self.y], [ARG_POS, ARG_OPT], [None, None],
                     AnyType(), False)
        assert_equal(str(c), 'def (X?, Y? =) -> Any')

        c2 = Callable([self.x, self.y], [ARG_OPT, ARG_OPT], [None, None],
                      AnyType(), False)
        assert_equal(str(c2), 'def (X? =, Y? =) -> Any')

    def test_callable_type_with_var_args(self):
        c = Callable([self.x], [ARG_STAR], [None], AnyType(), False)
        assert_equal(str(c), 'def (*X?) -> Any')

        c2 = Callable([self.x, self.y], [ARG_POS, ARG_STAR],
                      [None, None], AnyType(), False)
        assert_equal(str(c2), 'def (X?, *Y?) -> Any')

        c3 = Callable([self.x, self.y], [ARG_OPT, ARG_STAR], [None, None],
                      AnyType(), False)
        assert_equal(str(c3), 'def (X? =, *Y?) -> Any')

    def test_tuple_type(self):
        assert_equal(str(TupleType([])), 'Tuple[]')
        assert_equal(str(TupleType([self.x])), 'Tuple[X?]')
        assert_equal(str(TupleType([self.x, AnyType()])), 'Tuple[X?, Any]')

    def test_type_variable_binding(self):
        assert_equal(str(TypeVarDef('X', 1, None)), 'X')
        assert_equal(str(TypeVarDef('X', 1, [self.x, self.y])),
                     'X in (X?, Y?)')

    def test_generic_function_type(self):
        c = Callable([self.x, self.y], [ARG_POS, ARG_POS], [None, None],
                     self.y, False, None,
                     [TypeVarDef('X', -1, None)])
        assert_equal(str(c), 'def [X] (X?, Y?) -> Y?')

        v = [TypeVarDef('Y', -1, None), TypeVarDef('X', -2, None)]
        c2 = Callable([], [], [], Void(None), False, None, v)
        assert_equal(str(c2), 'def [Y, X] ()')


class TypeOpsSuite(Suite):
    def set_up(self):
        self.fx = TypeFixture()

    # expand_type

    def test_trivial_expand(self):
        for t in (self.fx.a, self.fx.o, self.fx.t, self.fx.void, self.fx.nonet,
                  self.tuple(self.fx.a),
                  self.callable([], self.fx.a, self.fx.a), self.fx.anyt):
            self.assert_expand(t, [], t)
            self.assert_expand(t, [], t)
            self.assert_expand(t, [], t)

    def test_expand_naked_type_var(self):
        self.assert_expand(self.fx.t, [(1, self.fx.a)], self.fx.a)
        self.assert_expand(self.fx.t, [(2, self.fx.a)], self.fx.t)

    def test_expand_basic_generic_types(self):
        self.assert_expand(self.fx.gt, [(1, self.fx.a)], self.fx.ga)

    # IDEA: Add test cases for
    #   tuple types
    #   callable types
    #   multiple arguments

    def assert_expand(self, orig, map_items, result):
        lower_bounds = {}

        for id, t in map_items:
            lower_bounds[id] = t

        exp = expand_type(orig, lower_bounds)
        # Remove erased tags (asterisks).
        assert_equal(str(exp).replace('*', ''), str(result))

    # replace_type_vars

    def test_trivial_replace(self):
        for t in (self.fx.a, self.fx.o, self.fx.void, self.fx.nonet,
                  self.tuple(self.fx.a),
                  self.callable([], self.fx.a, self.fx.a), self.fx.anyt,
                  self.fx.err):
            self.assert_replace(t, t)

    def test_replace_type_var(self):
        self.assert_replace(self.fx.t, self.fx.anyt)

    def test_replace_generic_instance(self):
        self.assert_replace(self.fx.ga, self.fx.ga)
        self.assert_replace(self.fx.gt, self.fx.gdyn)

    def assert_replace(self, orig, result):
        assert_equal(str(replace_type_vars(orig)), str(result))

    # erase_type

    def test_trivial_erase(self):
        for t in (self.fx.a, self.fx.o, self.fx.void, self.fx.nonet,
                  self.fx.anyt, self.fx.err):
            self.assert_erase(t, t)

    def test_erase_with_type_variable(self):
        self.assert_erase(self.fx.t, self.fx.anyt)

    def test_erase_with_generic_type(self):
        self.assert_erase(self.fx.ga, self.fx.gdyn)
        self.assert_erase(self.fx.hab,
                          Instance(self.fx.hi, [self.fx.anyt, self.fx.anyt]))

    def test_erase_with_tuple_type(self):
        self.assert_erase(self.tuple(self.fx.a), self.fx.std_tuple)

    def test_erase_with_function_type(self):
        self.assert_erase(self.fx.callable(self.fx.a, self.fx.b),
                          self.fx.callable_type(self.fx.void))

    def test_erase_with_type_object(self):
        self.assert_erase(self.fx.callable_type(self.fx.a, self.fx.b),
                          self.fx.callable_type(self.fx.void))

    def assert_erase(self, orig, result):
        assert_equal(str(erase_type(orig, self.fx.basic)), str(result))

    # is_more_precise

    def test_is_more_precise(self):
        fx = self.fx
        assert_true(is_more_precise(fx.b, fx.a))
        assert_true(is_more_precise(fx.b, fx.b))
        assert_true(is_more_precise(fx.b, fx.b))
        assert_true(is_more_precise(fx.b, fx.anyt))
        assert_true(is_more_precise(self.tuple(fx.b, fx.a),
                                    self.tuple(fx.b, fx.a)))

        assert_false(is_more_precise(fx.a, fx.b))
        assert_false(is_more_precise(fx.anyt, fx.b))
        assert_false(is_more_precise(self.tuple(fx.b, fx.b),
                                     self.tuple(fx.b, fx.a)))

    # is_proper_subtype

    def test_is_proper_subtype(self):
        fx = self.fx

        assert_true(is_proper_subtype(fx.a, fx.a))
        assert_true(is_proper_subtype(fx.b, fx.a))
        assert_true(is_proper_subtype(fx.b, fx.o))
        assert_true(is_proper_subtype(fx.b, fx.o))

        assert_false(is_proper_subtype(fx.a, fx.b))
        assert_false(is_proper_subtype(fx.o, fx.b))

        assert_true(is_proper_subtype(fx.anyt, fx.anyt))
        assert_false(is_proper_subtype(fx.a, fx.anyt))
        assert_false(is_proper_subtype(fx.anyt, fx.a))

        assert_true(is_proper_subtype(fx.ga, fx.ga))
        assert_true(is_proper_subtype(fx.gdyn, fx.gdyn))
        assert_true(is_proper_subtype(fx.gsab, fx.gb))
        assert_false(is_proper_subtype(fx.gsab, fx.ga))
        assert_false(is_proper_subtype(fx.gb, fx.ga))
        assert_false(is_proper_subtype(fx.ga, fx.gdyn))
        assert_false(is_proper_subtype(fx.gdyn, fx.ga))

        assert_true(is_proper_subtype(fx.t, fx.t))
        assert_false(is_proper_subtype(fx.t, fx.s))

    # Helpers

    def tuple(self, *a):
        return TupleType(a)

    def callable(self, vars, *a) -> Callable:
        """callable(args, a1, ..., an, r) constructs a callable with
        argument types a1, ... an and return type r and type arguments
        vars.
        """
        tv = []  # type: List[TypeVarDef]
        n = -1
        for v in vars:
            tv.append(TypeVarDef(v, n, None))
            n -= 1
        return Callable(a[:-1],
                        [ARG_POS] * (len(a) - 1),
                        [None] * (len(a) - 1),
                        a[-1],
                        False,
                        None,
                        tv)


class JoinSuite(Suite):
    def set_up(self):
        self.fx = TypeFixture()

    def test_trivial_cases(self):
        for simple in self.fx.void, self.fx.a, self.fx.o, self.fx.b:
            self.assert_join(simple, simple, simple)

    def test_class_subtyping(self):
        self.assert_join(self.fx.a, self.fx.o, self.fx.o)
        self.assert_join(self.fx.b, self.fx.o, self.fx.o)
        self.assert_join(self.fx.a, self.fx.d, self.fx.o)
        self.assert_join(self.fx.b, self.fx.c, self.fx.a)
        self.assert_join(self.fx.b, self.fx.d, self.fx.o)

    def test_tuples(self):
        self.assert_join(self.tuple(), self.tuple(), self.tuple())
        self.assert_join(self.tuple(self.fx.a),
                         self.tuple(self.fx.a),
                         self.tuple(self.fx.a))
        self.assert_join(self.tuple(self.fx.b, self.fx.c),
                         self.tuple(self.fx.a, self.fx.d),
                         self.tuple(self.fx.a, self.fx.o))

        self.assert_join(self.tuple(self.fx.a, self.fx.a),
                         self.fx.std_tuple,
                         self.fx.o)
        self.assert_join(self.tuple(self.fx.a),
                         self.tuple(self.fx.a, self.fx.a),
                         self.fx.o)

    def test_function_types(self):
        self.assert_join(self.callable(self.fx.a, self.fx.b),
                         self.callable(self.fx.a, self.fx.b),
                         self.callable(self.fx.a, self.fx.b))

        self.assert_join(self.callable(self.fx.a, self.fx.b),
                         self.callable(self.fx.b, self.fx.b),
                         self.fx.o)
        self.assert_join(self.callable(self.fx.a, self.fx.b),
                         self.callable(self.fx.a, self.fx.a),
                         self.fx.o)

    def test_type_vars(self):
        self.assert_join(self.fx.t, self.fx.t, self.fx.t)
        self.assert_join(self.fx.s, self.fx.s, self.fx.s)
        self.assert_join(self.fx.t, self.fx.s, self.fx.o)

    def test_void(self):
        self.assert_join(self.fx.void, self.fx.void, self.fx.void)
        self.assert_join(self.fx.void, self.fx.anyt, self.fx.anyt)

        # Join of any other type against void results in ErrorType, since there
        # is no other meaningful result.
        for t in [self.fx.a, self.fx.o, NoneTyp(), UnboundType('x'),
                  self.fx.t, self.tuple(),
                  self.callable(self.fx.a, self.fx.b)]:
            self.assert_join(t, self.fx.void, self.fx.err)

    def test_none(self):
        # Any type t joined with None results in t.
        for t in [NoneTyp(), self.fx.a, self.fx.o, UnboundType('x'),
                  self.fx.t, self.tuple(),
                  self.callable(self.fx.a, self.fx.b), self.fx.anyt]:
            self.assert_join(t, NoneTyp(), t)

    def test_unbound_type(self):
        self.assert_join(UnboundType('x'), UnboundType('x'), self.fx.anyt)
        self.assert_join(UnboundType('x'), UnboundType('y'), self.fx.anyt)

        # Any type t joined with an unbound type results in dynamic. Unbound
        # type means that there is an error somewhere in the program, so this
        # does not affect type safety (whatever the result).
        for t in [self.fx.a, self.fx.o, self.fx.ga, self.fx.t, self.tuple(),
                  self.callable(self.fx.a, self.fx.b)]:
            self.assert_join(t, UnboundType('X'), self.fx.anyt)

    def test_any_type(self):
        # Join against 'Any' type always results in 'Any'.
        for t in [self.fx.anyt, self.fx.a, self.fx.o, NoneTyp(),
                  UnboundType('x'), self.fx.void, self.fx.t, self.tuple(),
                  self.callable(self.fx.a, self.fx.b)]:
            self.assert_join(t, self.fx.anyt, self.fx.anyt)

    def test_other_mixed_types(self):
        # In general, joining unrelated types produces object.
        for t1 in [self.fx.a, self.fx.t, self.tuple(),
                   self.callable(self.fx.a, self.fx.b)]:
            for t2 in [self.fx.a, self.fx.t, self.tuple(),
                       self.callable(self.fx.a, self.fx.b)]:
                if str(t1) != str(t2):
                    self.assert_join(t1, t2, self.fx.o)

    def test_error_type(self):
        self.assert_join(self.fx.err, self.fx.anyt, self.fx.anyt)

        # Meet against any type except dynamic results in ErrorType.
        for t in [self.fx.a, self.fx.o, NoneTyp(), UnboundType('x'),
                  self.fx.void, self.fx.t, self.tuple(),
                  self.callable(self.fx.a, self.fx.b)]:
            self.assert_join(t, self.fx.err, self.fx.err)

    def test_simple_generics(self):
        self.assert_join(self.fx.ga, self.fx.ga, self.fx.ga)
        self.assert_join(self.fx.ga, self.fx.gb, self.fx.o)
        self.assert_join(self.fx.ga, self.fx.g2a, self.fx.o)

        self.assert_join(self.fx.ga, self.fx.nonet, self.fx.ga)
        self.assert_join(self.fx.ga, self.fx.anyt, self.fx.anyt)

        for t in [self.fx.a, self.fx.o, self.fx.t, self.tuple(),
                  self.callable(self.fx.a, self.fx.b)]:
            self.assert_join(t, self.fx.ga, self.fx.o)

    def test_generics_with_multiple_args(self):
        self.assert_join(self.fx.hab, self.fx.hab, self.fx.hab)
        self.assert_join(self.fx.hab, self.fx.haa, self.fx.o)
        self.assert_join(self.fx.hab, self.fx.hbb, self.fx.o)

    def test_generics_with_inheritance(self):
        self.assert_join(self.fx.gsab, self.fx.gb, self.fx.gb)
        self.assert_join(self.fx.gsba, self.fx.gb, self.fx.o)

    def test_generics_with_inheritance_and_shared_supertype(self):
        self.assert_join(self.fx.gsba, self.fx.gs2a, self.fx.ga)
        self.assert_join(self.fx.gsab, self.fx.gs2a, self.fx.o)

    def test_generic_types_and_any(self):
        self.assert_join(self.fx.gdyn, self.fx.ga, self.fx.gdyn)

    def test_callables_with_any(self):
        self.assert_join(self.callable(self.fx.a, self.fx.a, self.fx.anyt,
                                       self.fx.a),
                         self.callable(self.fx.a, self.fx.anyt, self.fx.a,
                                       self.fx.anyt),
                         self.callable(self.fx.a, self.fx.anyt, self.fx.anyt,
                                       self.fx.anyt))

    def test_join_interface_types(self):
        self.skip()  # FIX
        self.assert_join(self.fx.f, self.fx.f, self.fx.f)
        self.assert_join(self.fx.f, self.fx.f2, self.fx.o)
        self.assert_join(self.fx.f, self.fx.f3, self.fx.f)

    def test_join_interface_and_class_types(self):
        self.skip()  # FIX

        self.assert_join(self.fx.o, self.fx.f, self.fx.o)
        self.assert_join(self.fx.a, self.fx.f, self.fx.o)

        self.assert_join(self.fx.e, self.fx.f, self.fx.f)

    def test_join_class_types_with_interface_result(self):
        self.skip()  # FIX
        # Unique result
        self.assert_join(self.fx.e, self.fx.e2, self.fx.f)

        # Ambiguous result
        self.assert_join(self.fx.e2, self.fx.e3, self.fx.err)

    def test_generic_interfaces(self):
        self.skip()  # FIX

        fx = InterfaceTypeFixture()

        self.assert_join(fx.gfa, fx.gfa, fx.gfa)
        self.assert_join(fx.gfa, fx.gfb, fx.o)

        self.assert_join(fx.m1, fx.gfa, fx.gfa)

        self.assert_join(fx.m1, fx.gfb, fx.o)

    def test_simple_type_objects(self):
        t1 = self.type_callable(self.fx.a, self.fx.a)
        t2 = self.type_callable(self.fx.b, self.fx.b)

        self.assert_join(t1, t1, t1)
        assert_true(join_types(t1, t1, self.fx.basic).is_type_obj())

        self.assert_join(t1, t2, self.fx.type_type)
        self.assert_join(t1, self.fx.type_type, self.fx.type_type)
        self.assert_join(self.fx.type_type, self.fx.type_type,
                         self.fx.type_type)

    # There are additional test cases in check-inference.test.

    # FIX interfaces with different paths

    # FIX generic interfaces + inheritance
    # FIX generic interfaces + ranges

    # FIX function types + varargs and default args

    def assert_join(self, s, t, join):
        self.assert_simple_join(s, t, join)
        self.assert_simple_join(t, s, join)

    def assert_simple_join(self, s, t, join):
        result = join_types(s, t, self.fx.basic)
        actual = str(result)
        expected = str(join)
        assert_equal(actual, expected,
                     'join({}, {}) == {{}} ({{}} expected)'.format(s, t))
        if not isinstance(s, ErrorType) and not isinstance(result, ErrorType):
            assert_true(is_subtype(s, result),
                        '{} not subtype of {}'.format(s, result))
        if not isinstance(t, ErrorType) and not isinstance(result, ErrorType):
            assert_true(is_subtype(t, result),
                        '{} not subtype of {}'.format(t, result))

    def tuple(self, *a):
        return TupleType(a)

    def callable(self, *a):
        """callable(a1, ..., an, r) constructs a callable with argument types
        a1, ... an and return type r.
        """
        n = len(a) - 1
        return Callable(a[:-1], [ARG_POS] * n, [None] * n,
                        a[-1], False)

    def type_callable(self, *a):
        """type_callable(a1, ..., an, r) constructs a callable with
        argument types a1, ... an and return type r, and which
        represents a type.
        """
        n = len(a) - 1
        return Callable(a[:-1], [ARG_POS] * n, [None] * n,
                        a[-1], True)


class MeetSuite(Suite):
    def set_up(self):
        self.fx = TypeFixture()

    def test_trivial_cases(self):
        for simple in self.fx.void, self.fx.a, self.fx.o, self.fx.b:
            self.assert_meet(simple, simple, simple)

    def test_class_subtyping(self):
        self.assert_meet(self.fx.a, self.fx.o, self.fx.a)
        self.assert_meet(self.fx.a, self.fx.b, self.fx.b)
        self.assert_meet(self.fx.b, self.fx.o, self.fx.b)
        self.assert_meet(self.fx.a, self.fx.d, NoneTyp())
        self.assert_meet(self.fx.b, self.fx.c, NoneTyp())

    def test_tuples(self):
        self.assert_meet(self.tuple(), self.tuple(), self.tuple())
        self.assert_meet(self.tuple(self.fx.a),
                         self.tuple(self.fx.a),
                         self.tuple(self.fx.a))
        self.assert_meet(self.tuple(self.fx.b, self.fx.c),
                         self.tuple(self.fx.a, self.fx.d),
                         self.tuple(self.fx.b, NoneTyp()))

        self.assert_meet(self.tuple(self.fx.a, self.fx.a),
                         self.fx.std_tuple,
                         NoneTyp())
        self.assert_meet(self.tuple(self.fx.a),
                         self.tuple(self.fx.a, self.fx.a),
                         NoneTyp())

    def test_function_types(self):
        self.assert_meet(self.callable(self.fx.a, self.fx.b),
                         self.callable(self.fx.a, self.fx.b),
                         self.callable(self.fx.a, self.fx.b))

        self.assert_meet(self.callable(self.fx.a, self.fx.b),
                         self.callable(self.fx.b, self.fx.b),
                         NoneTyp())
        self.assert_meet(self.callable(self.fx.a, self.fx.b),
                         self.callable(self.fx.a, self.fx.a),
                         NoneTyp())

    def test_type_vars(self):
        self.assert_meet(self.fx.t, self.fx.t, self.fx.t)
        self.assert_meet(self.fx.s, self.fx.s, self.fx.s)
        self.assert_meet(self.fx.t, self.fx.s, NoneTyp())

    def test_void(self):
        self.assert_meet(self.fx.void, self.fx.void, self.fx.void)
        self.assert_meet(self.fx.void, self.fx.anyt, self.fx.void)

        # Meet of any other type against void results in ErrorType, since there
        # is no meaningful valid result.
        for t in [self.fx.a, self.fx.o, UnboundType('x'), NoneTyp(),
                  self.fx.t, self.tuple(),
                  self.callable(self.fx.a, self.fx.b)]:
            self.assert_meet(t, self.fx.void, self.fx.err)

    def test_none(self):
        self.assert_meet(NoneTyp(), NoneTyp(), NoneTyp())

        self.assert_meet(NoneTyp(), self.fx.anyt, NoneTyp())
        self.assert_meet(NoneTyp(), self.fx.void, self.fx.err)

        # Any type t joined with None results in None, unless t is any or
        # void.
        for t in [self.fx.a, self.fx.o, UnboundType('x'), self.fx.t,
                  self.tuple(), self.callable(self.fx.a, self.fx.b)]:
            self.assert_meet(t, NoneTyp(), NoneTyp())

    def test_unbound_type(self):
        self.assert_meet(UnboundType('x'), UnboundType('x'), self.fx.anyt)
        self.assert_meet(UnboundType('x'), UnboundType('y'), self.fx.anyt)

        self.assert_meet(UnboundType('x'), self.fx.void, self.fx.err)
        self.assert_meet(UnboundType('x'), self.fx.anyt, UnboundType('x'))

        # The meet of any type t with an unbound type results in dynamic
        # (except for void). Unbound type means that there is an error
        # somewhere in the program, so this does not affect type safety.
        for t in [self.fx.a, self.fx.o, self.fx.t, self.tuple(),
                  self.callable(self.fx.a, self.fx.b)]:
            self.assert_meet(t, UnboundType('X'), self.fx.anyt)

    def test_dynamic_type(self):
        # Meet against dynamic type always results in dynamic.
        for t in [self.fx.anyt, self.fx.a, self.fx.o, NoneTyp(),
                  UnboundType('x'), self.fx.void, self.fx.t, self.tuple(),
                  self.callable(self.fx.a, self.fx.b)]:
            self.assert_meet(t, self.fx.anyt, t)

    def test_error_type(self):
        self.assert_meet(self.fx.err, self.fx.anyt, self.fx.err)

        # Meet against any type except dynamic results in ErrorType.
        for t in [self.fx.a, self.fx.o, NoneTyp(), UnboundType('x'),
                  self.fx.void, self.fx.t, self.tuple(),
                  self.callable(self.fx.a, self.fx.b)]:
            self.assert_meet(t, self.fx.err, self.fx.err)

    def test_simple_generics(self):
        self.assert_meet(self.fx.ga, self.fx.ga, self.fx.ga)
        self.assert_meet(self.fx.ga, self.fx.o, self.fx.ga)
        self.assert_meet(self.fx.ga, self.fx.gb, self.fx.nonet)
        self.assert_meet(self.fx.ga, self.fx.g2a, self.fx.nonet)

        self.assert_meet(self.fx.ga, self.fx.nonet, self.fx.nonet)
        self.assert_meet(self.fx.ga, self.fx.anyt, self.fx.ga)

        for t in [self.fx.a, self.fx.t, self.tuple(),
                  self.callable(self.fx.a, self.fx.b)]:
            self.assert_meet(t, self.fx.ga, self.fx.nonet)

    def test_generics_with_multiple_args(self):
        self.assert_meet(self.fx.hab, self.fx.hab, self.fx.hab)
        self.assert_meet(self.fx.hab, self.fx.haa, self.fx.nonet)
        self.assert_meet(self.fx.hab, self.fx.hbb, self.fx.nonet)

    def test_generics_with_inheritance(self):
        self.assert_meet(self.fx.gsab, self.fx.gb, self.fx.gsab)
        self.assert_meet(self.fx.gsba, self.fx.gb, self.fx.nonet)

    def test_generics_with_inheritance_and_shared_supertype(self):
        self.assert_meet(self.fx.gsba, self.fx.gs2a, self.fx.nonet)
        self.assert_meet(self.fx.gsab, self.fx.gs2a, self.fx.nonet)

    def test_generic_types_and_dynamic(self):
        self.assert_meet(self.fx.gdyn, self.fx.ga, self.fx.ga)

    def test_callables_with_dynamic(self):
        self.assert_meet(self.callable(self.fx.a, self.fx.a, self.fx.anyt,
                                       self.fx.a),
                         self.callable(self.fx.a, self.fx.anyt, self.fx.a,
                                       self.fx.anyt),
                         self.callable(self.fx.a, self.fx.anyt, self.fx.anyt,
                                       self.fx.anyt))

    def test_meet_interface_types(self):
        self.assert_meet(self.fx.f, self.fx.f, self.fx.f)
        self.assert_meet(self.fx.f, self.fx.f2, self.fx.nonet)
        self.assert_meet(self.fx.f, self.fx.f3, self.fx.f3)

    def test_join_interface_and_class_types(self):
        self.assert_meet(self.fx.o, self.fx.f, self.fx.f)
        self.assert_meet(self.fx.a, self.fx.f, self.fx.nonet)

        self.assert_meet(self.fx.e, self.fx.f, self.fx.e)

    def test_join_class_types_with_shared_interfaces(self):
        # These have nothing special with respect to meets, unlike joins. These
        # are for completeness only.
        self.assert_meet(self.fx.e, self.fx.e2, self.fx.nonet)
        self.assert_meet(self.fx.e2, self.fx.e3, self.fx.nonet)

    def test_meet_with_generic_interfaces(self):
        # TODO fix
        self.skip()

        fx = InterfaceTypeFixture()
        self.assert_meet(fx.gfa, fx.m1, fx.m1)
        self.assert_meet(fx.gfa, fx.gfa, fx.gfa)
        self.assert_meet(fx.gfb, fx.m1, fx.nonet)

    # FIX generic interfaces + ranges

    def assert_meet(self, s, t, meet):
        self.assert_simple_meet(s, t, meet)
        self.assert_simple_meet(t, s, meet)

    def assert_simple_meet(self, s, t, meet):
        result = meet_types(s, t, self.fx.basic)
        actual = str(result)
        expected = str(meet)
        assert_equal(actual, expected,
                     'meet({}, {}) == {{}} ({{}} expected)'.format(s, t))
        if not isinstance(s, ErrorType) and not isinstance(result, ErrorType):
            assert_true(is_subtype(result, s),
                        '{} not subtype of {}'.format(result, s))
        if not isinstance(t, ErrorType) and not isinstance(result, ErrorType):
            assert_true(is_subtype(result, t),
                        '{} not subtype of {}'.format(result, t))

    def tuple(self, *a):
        return TupleType(a)

    def callable(self, *a):
        """callable(a1, ..., an, r) constructs a callable with argument types
        a1, ... an and return type r.
        """
        n = len(a) - 1
        return Callable(a[:-1],
                        [ARG_POS] * n, [None] * n,
                        a[-1], False)


class CombinedTypesSuite(Suite):
    def __init__(self):
        self.test_types = TypesSuite()
        self.test_type_ops = TypeOpsSuite()
        self.test_join = JoinSuite()
        self.test_meet = MeetSuite()
        super().__init__()


if __name__ == '__main__':
    import sys
    run_test(CombinedTypesSuite(), sys.argv[1:])
