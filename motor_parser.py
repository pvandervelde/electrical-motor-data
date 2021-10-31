import math
import yaml

from typing import Tuple
from pydantic import BaseModel, HttpUrl

class Dimension(BaseModel):
    length: float
    diameter: float
    weight: float

class Manufacturer(BaseModel):
    name: str
    url: HttpUrl

class MotorPerformance(BaseModel):
    free_running_current: float
    kv: float
    max_rpm: int
    max_voltage: float
    power: float
    stall_current: float
    stall_torque: float
    url: HttpUrl

class MotorPerformanceCollection(BaseModel):
    published: MotorPerformance
    measured: MotorPerformance = None

class Price(BaseModel):
    currency: str
    value: float

class MotorType(BaseModel):
    power_source: str
    brushes: bool
    runner: str

class Motor(BaseModel):
    name: str
    sku: str
    url: HttpUrl
    dimensions: Dimension
    manufacturer: Manufacturer
    performance: MotorPerformanceCollection
    price: Price
    type: MotorType

def parse_config(path: str) -> Motor:
    with open(path, 'r') as f:
        valuesYaml = yaml.load(f, Loader=yaml.FullLoader)

    return Motor.parse_obj(valuesYaml)

class Gear:
    def __init__(self, ratio: float):
        self.ratio = ratio

class GearPerformance:
    def __init__(self, gear: Gear, torque: float, velocity_in_rpm: float):
        self.gear = gear
        self.torque = torque
        self.velocity_in_rpm = velocity_in_rpm


def gearing_for_motor(motor: Motor, required_power: float, required_torque: float, required_velocity_in_rpm: float) -> Tuple[GearPerformance, GearPerformance]:
    power_min_velocity_in_rpm, power_max_velocity_in_rpm = velocity_boundaries_for_required_power(motor, required_power)

    # If one of the numbers is NaN then we either have no possible match or 1 possible match
    # If there is one possible match then we hit exactly maximum power. That seems unsafe so ignore it
    if math.isnan(power_max_velocity_in_rpm):
        return GearPerformance(Gear(0.0)), GearPerformance(Gear(0.0))

    min_gearing, max_gearing = gear_ratio_for_torque_and_velocity(motor, required_torque, required_velocity_in_rpm)

    min_gear_performance = GearPerformance(Gear(min_gearing), required_torque, power_min_velocity_in_rpm / min_gearing)
    max_gear_performance = GearPerformance(Gear(max_gearing), required_torque, power_max_velocity_in_rpm / max_gearing)

    return min_gear_performance, max_gear_performance

def velocity_boundaries_for_required_power(motor: Motor, required_power: float) -> Tuple[float, float]:
    # The power curve for a motor is
    # - 0.0 at 0 speed
    # - 0.0 at maximum speed
    # - Maximum power at half speed
    #
    # The power function is
    #
    # P = - (4 * Power_max / velocity_max^2) * velocity^2 + (4 * Power_max / velocity_max) * velocity
    #
    # Solves by
    #
    # velocity = (-b +- Sqrt(b^2 - 4*a*c))/(2 * a)

    a = -4 * motor.performance.published.power / (motor.performance.published.max_rpm * motor.performance.published.max_rpm)
    b = 4 * motor.performance.published.power / motor.performance.published.max_rpm
    c = -required_power

    return solve_quadratic_equation(a, b, c)

def gear_ratio_for_torque_and_velocity(motor: Motor, required_torque: float, required_velocity_in_rpm: float) -> float:
    # The velocity equation for gearing is
    #
    #     v_motor = v_required * gear_ratio
    #
    # The torque equation for gearing is
    #
    #    t_required = gear_ratio * (t_stall - t_stall / velocity_max * velocity_motor)
    #
    # Solving for gear_ratio leads to
    #
    #   0 = - t_stall / velocity_max * v_required * gear_ratio^2 + gear_ratio * t_stall - t_required
    perf = motor.performance.published
    a = - perf.stall_torque / perf.max_rpm * required_velocity_in_rpm
    b = perf.stall_torque
    c = - required_torque

    return solve_quadratic_equation(a, b, c)

def solve_quadratic_equation(a: float, b: float, c:float) -> Tuple[float, float]:
    discriminant = b * b - 4 * a * c

    if discriminant < 0:
        # We don't care about complex solutions for this equation
        return math.nan, math.nan
    elif discriminant == 0:
        x = (-b + math.sqrt( b**2 - 4*a*c)) / 2*a
        return x, math.nan
    else:
        x1 = (-b + math.sqrt((b**2) - (4*(a*c))))/(2*a)
        x2 = (-b - math.sqrt((b**2) - (4*(a*c))))/(2*a)
        return x1, x2