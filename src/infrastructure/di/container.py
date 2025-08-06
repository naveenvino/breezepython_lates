"""
Dependency Injection Container
Manages service dependencies and lifecycle
"""
import logging
from typing import Dict, Any, Type, TypeVar, Optional, Callable

from ...domain.repositories.imarket_data_repository import IMarketDataRepository
from ...domain.repositories.ioptions_repository import IOptionsRepository, IOptionsHistoricalDataRepository
from ...domain.repositories.itrade_repository import ITradeRepository
from ...domain.services.iprice_calculator import IPriceCalculator
from ...domain.services.irisk_manager import IRiskManager

from ...application.interfaces.idata_collector import IDataCollector
from ...application.interfaces.ibacktest_engine import IBacktestEngine
from ...application.interfaces.istrategy_manager import IStrategyManager
from ...application.interfaces.inotification_service import INotificationService

from ..repositories.market_data_repository import MarketDataRepository
from ..repositories.options_repository import OptionsRepository, OptionsHistoricalDataRepository
from ..repositories.trade_repository import TradeRepository
from ..services.breeze_data_collector import BreezeDataCollector
from ..services.price_calculator_service import BlackScholesPriceCalculator
from ..services.risk_manager_service import RiskManagerService

from ...application.use_cases.collect_weekly_data_use_case import CollectWeeklyDataUseCase
from ...application.use_cases.analyze_data_availability_use_case import AnalyzeDataAvailabilityUseCase
from ...application.use_cases.fetch_option_chain_use_case import FetchOptionChainUseCase, AnalyzeOptionChainUseCase
from ...application.use_cases.run_backtest import RunBacktestUseCase
from ..services.data_collection_service import DataCollectionService
from ..services.option_pricing_service import OptionPricingService
from ..services.breeze_service import BreezeService

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ServiceContainer:
    """Dependency injection container"""
    
    def __init__(self):
        self._services: Dict[Type, Any] = {}
        self._factories: Dict[Type, Callable] = {}
        self._singletons: Dict[Type, Any] = {}
        self._register_services()
    
    def _register_services(self):
        """Register all services and their implementations"""
        # Register repositories
        self.register_singleton(IMarketDataRepository, MarketDataRepository)
        self.register_singleton(IOptionsRepository, OptionsRepository)
        self.register_singleton(IOptionsHistoricalDataRepository, OptionsHistoricalDataRepository)
        self.register_singleton(ITradeRepository, TradeRepository)
        
        # Register domain services
        self.register_singleton(IPriceCalculator, BlackScholesPriceCalculator)
        self.register_singleton(IRiskManager, RiskManagerService)
        
        # Register application services
        self.register_singleton(IDataCollector, BreezeDataCollector)
        
        # Register new services
        self.register_singleton(BreezeService, BreezeService)
        # Changed to factory to avoid caching issues
        self.register_factory(DataCollectionService, lambda: DataCollectionService(
            breeze_service=self.resolve(BreezeService),
            db_manager=None  # Will use get_db_manager() internally
        ))
        self.register_factory(OptionPricingService, lambda: OptionPricingService(
            data_collection_service=self.resolve(DataCollectionService),
            db_manager=None  # Will use get_db_manager() internally
        ))
        self.register_factory("DataCollectionService", lambda: self.resolve(DataCollectionService))
        
        # Register use cases as transient
        self.register_factory(CollectWeeklyDataUseCase, self._create_collect_weekly_data_use_case)
        self.register_factory(AnalyzeDataAvailabilityUseCase, self._create_analyze_data_availability_use_case)
        self.register_factory(FetchOptionChainUseCase, self._create_fetch_option_chain_use_case)
        self.register_factory(AnalyzeOptionChainUseCase, self._create_analyze_option_chain_use_case)
        self.register_factory(RunBacktestUseCase, self._create_run_backtest_use_case)
    
    def register(self, interface: Type[T], implementation: Type[T]) -> None:
        """Register a service"""
        self._services[interface] = implementation
        logger.debug(f"Registered {interface.__name__} -> {implementation.__name__}")
    
    def register_singleton(self, interface, implementation) -> None:
        """Register a singleton service"""
        self._services[interface] = implementation
        if hasattr(interface, '__name__'):
            if hasattr(implementation, '__name__'):
                logger.debug(f"Registered singleton {interface.__name__} -> {implementation.__name__}")
            else:
                logger.debug(f"Registered singleton {interface.__name__} -> lambda factory")
        else:
            logger.debug(f"Registered singleton {interface} -> {implementation}")
    
    def register_factory(self, service_type: Type[T], factory: Callable[[], T]) -> None:
        """Register a factory function for a service"""
        self._factories[service_type] = factory
        if hasattr(service_type, '__name__'):
            logger.debug(f"Registered factory for {service_type.__name__}")
        else:
            logger.debug(f"Registered factory for {service_type}")
    
    def resolve(self, service_type) -> Any:
        """Resolve a service instance"""
        # Handle string-based resolution
        if isinstance(service_type, str):
            for key in self._services:
                if hasattr(key, '__name__') and key.__name__ == service_type:
                    service_type = key
                    break
            else:
                # Check direct string keys or create from class name
                if service_type in self._services:
                    implementation = self._services[service_type]
                    if callable(implementation):
                        return implementation()
                    return implementation
                # Try to find by class name
                for svc_type, impl in self._services.items():
                    if hasattr(svc_type, '__name__') and svc_type.__name__ == service_type:
                        if callable(impl):
                            instance = impl()
                        else:
                            instance = impl() if hasattr(impl, '__call__') else impl
                        self._singletons[svc_type] = instance
                        return instance
                raise ValueError(f"Service {service_type} not registered")
        
        # Check if it's a factory
        if service_type in self._factories:
            return self._factories[service_type]()
        
        # Check if it's already instantiated as singleton
        if service_type in self._singletons:
            return self._singletons[service_type]
        
        # Check if it's registered
        if service_type in self._services:
            implementation = self._services[service_type]
            if callable(implementation):
                instance = implementation()
            elif hasattr(implementation, '__call__'):
                instance = implementation()
            else:
                instance = implementation()
            
            # Store singleton
            self._singletons[service_type] = instance
            return instance
        
        # Try to resolve by exact type match
        for interface, implementation in self._services.items():
            if interface == service_type:
                if callable(implementation):
                    instance = implementation()
                else:
                    instance = implementation
                self._singletons[service_type] = instance
                return instance
        
        raise ValueError(f"Service {service_type.__name__ if hasattr(service_type, '__name__') else service_type} not registered")
    
    def resolve_all(self, service_type: Type[T]) -> list[T]:
        """Resolve all implementations of a service type"""
        implementations = []
        
        for interface, implementation in self._services.items():
            if issubclass(interface, service_type):
                if interface in self._singletons:
                    implementations.append(self._singletons[interface])
                else:
                    instance = implementation()
                    self._singletons[interface] = instance
                    implementations.append(instance)
        
        return implementations
    
    # Factory methods for use cases
    
    def _create_collect_weekly_data_use_case(self) -> CollectWeeklyDataUseCase:
        """Create CollectWeeklyDataUseCase with dependencies"""
        return CollectWeeklyDataUseCase(
            data_collector=self.resolve(IDataCollector),
            market_data_repo=self.resolve(IMarketDataRepository),
            options_data_repo=self.resolve(IOptionsHistoricalDataRepository)
        )
    
    def _create_analyze_data_availability_use_case(self) -> AnalyzeDataAvailabilityUseCase:
        """Create AnalyzeDataAvailabilityUseCase with dependencies"""
        return AnalyzeDataAvailabilityUseCase(
            market_data_repo=self.resolve(IMarketDataRepository),
            options_data_repo=self.resolve(IOptionsHistoricalDataRepository)
        )
    
    def _create_fetch_option_chain_use_case(self) -> FetchOptionChainUseCase:
        """Create FetchOptionChainUseCase with dependencies"""
        return FetchOptionChainUseCase(
            data_collector=self.resolve(IDataCollector),
            options_repo=self.resolve(IOptionsRepository),
            market_data_repo=self.resolve(IMarketDataRepository)
        )
    
    def _create_analyze_option_chain_use_case(self) -> AnalyzeOptionChainUseCase:
        """Create AnalyzeOptionChainUseCase with dependencies"""
        return AnalyzeOptionChainUseCase(
            options_repo=self.resolve(IOptionsRepository),
            market_data_repo=self.resolve(IMarketDataRepository),
            price_calculator=self.resolve(IPriceCalculator)
        )
    
    def _create_run_backtest_use_case(self) -> RunBacktestUseCase:
        """Create RunBacktestUseCase with dependencies"""
        return RunBacktestUseCase(
            data_collection_service=self.resolve(DataCollectionService),
            option_pricing_service=self.resolve(OptionPricingService)
        )


# Global container instance
_container: Optional[ServiceContainer] = None


def get_container() -> ServiceContainer:
    """Get the global service container"""
    global _container
    if _container is None:
        _container = ServiceContainer()
    return _container


def get_service(service_type: Type[T]) -> T:
    """Get a service from the container"""
    container = get_container()
    return container.resolve(service_type)


def inject(**dependencies):
    """Decorator for dependency injection"""
    def decorator(cls):
        original_init = cls.__init__
        
        def new_init(self, **kwargs):
            # Inject dependencies
            container = get_container()
            for name, service_type in dependencies.items():
                if name not in kwargs:
                    kwargs[name] = container.resolve(service_type)
            
            # Call original init
            original_init(self, **kwargs)
        
        cls.__init__ = new_init
        return cls
    
    return decorator