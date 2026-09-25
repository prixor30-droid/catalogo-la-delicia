/* Service worker del catálogo de La Delicia.

   Sirve para que el catálogo abra al instante y siga funcionando donde no hay
   señal, que es justo lo que pasa dentro de muchas tiendas.

   La regla importante está en cómo se guarda cada cosa:

   - El HTML (los precios) va SIEMPRE a la red primero. Si se cambia un precio
     y se sube, el cliente lo ve en cuanto abra con datos. La copia guardada
     solo se usa si no hay señal.
   - Las fotos y las fuentes se muestran de la copia guardada, rápido, y se
     revisan por detrás. Si se reemplazó una foto sin cambiarle el nombre, la
     nueva entra en la siguiente apertura. */

var CACHE = 'la-delicia-v8';

/* Lo mínimo para que el catálogo abra sin señal la primera vez. Las fotos no
   van aquí: son 1,5 MB y se irían a bajar todas de golpe en la instalación.
   Se van guardando solas a medida que el cliente las ve. */
var BASE = [
  './',
  './index.html',
  './manifest.json',
  './favicon-192.png',
  './favicon-512.png',
  './ladelicialogo.webp',
  './qr-catalogo.png'
];

self.addEventListener('install', function(e){
  e.waitUntil(
    caches.open(CACHE)
      .then(function(c){ return c.addAll(BASE); })
      // si un archivo de la lista falla, no se cae la instalación entera
      .catch(function(){})
      .then(function(){ return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function(e){
  e.waitUntil(
    caches.keys().then(function(nombres){
      return Promise.all(nombres.map(function(n){
        if (n !== CACHE) return caches.delete(n);
      }));
    }).then(function(){ return self.clients.claim(); })
  );
});

function guardar(pedido, respuesta){
  // las respuestas opacas y los errores no se guardan: taparían la buena
  if (!respuesta || respuesta.status !== 200) return respuesta;
  var copia = respuesta.clone();
  caches.open(CACHE).then(function(c){ c.put(pedido, copia); });
  return respuesta;
}

self.addEventListener('fetch', function(e){
  var pedido = e.request;
  if (pedido.method !== 'GET') return;

  var url = new URL(pedido.url);
  var propio = url.origin === self.location.origin;
  var fuentes = url.hostname === 'fonts.googleapis.com' ||
                url.hostname === 'fonts.gstatic.com';
  if (!propio && !fuentes) return;   // lo demás va directo a la red

  /* HTML: red primero, para que los precios nunca salgan viejos. */
  if (pedido.mode === 'navigate' || (propio && url.pathname.endsWith('.html'))){
    e.respondWith(
      fetch(pedido)
        .then(function(r){ return guardar(pedido, r); })
        .catch(function(){
          return caches.match(pedido).then(function(c){
            return c || caches.match('./index.html');
          });
        })
    );
    return;
  }

  /* Fotos, fuentes y demás: se muestra la copia guardada de una y se revisa
     por detrás si cambió. */
  e.respondWith(
    caches.match(pedido).then(function(guardada){
      var red = fetch(pedido)
        .then(function(r){ return guardar(pedido, r); })
        .catch(function(){ return guardada; });
      return guardada || red;
    })
  );
});
