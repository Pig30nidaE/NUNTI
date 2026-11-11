"""Author and rasterize local Skin V2 artwork. Uses only local SVG and approved A layers."""
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'prototypes/avatar_generator/skin-v2'
SOURCE = ROOT / 'backend/nunti/avatar_studio/assets/nunti-a-layers-v1'
CHROME = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
SIZE = 768
ORDER = ('outfit', 'head', 'eyes', 'accessory')
SKINS = ('sea', 'city', 'mountain')


def gradient(name: str, *colors: str, horizontal: bool = False) -> str:
    stops = ''.join(f'<stop offset="{i / (len(colors) - 1):.3f}" stop-color="{color}"/>'
                    for i, color in enumerate(colors))
    end = '100%" y2="20%' if horizontal else '35%" y2="100%'
    return f'<linearGradient id="{name}" x1="0" y1="0" x2="{end}">{stops}</linearGradient>'


def svg(paths: str, defs: str = '') -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="768" height="768" viewBox="0 0 768 768"><defs>{defs}</defs>{paths}</svg>\n'


def fit_paths(body: str, palette: dict[str, tuple[str, ...]]) -> str:
    return svg(body, ''.join(gradient(name, *colors) for name, colors in palette.items()))


SEA_OUTFIT = fit_paths('''
<!-- Sailor trousers and flat deck shoes -->
<path fill="url(#trouser)" d="M278 540Q380 526 486 541L498 631Q495 657 471 660L406 660Q386 652 383 610Q378 655 361 661H294Q268 658 268 632Z"/>
<path d="M285 629Q329 638 375 629M392 629Q437 637 487 630" stroke="#366074" stroke-width="3" fill="none" opacity=".38"/>
<g fill="url(#sole)">
 <path d="M280 650Q322 637 365 649Q382 668 377 697Q373 717 351 719H273Q246 717 245 696Q246 669 280 650Z"/>
 <path d="M400 650Q445 637 483 650Q515 663 521 691Q525 717 498 719H422Q396 716 393 700Q388 673 400 650Z"/>
</g>
<g fill="url(#sand)">
 <path d="M279 650Q318 638 363 647Q377 663 372 690Q328 703 251 692Q256 664 279 650Z"/>
 <path d="M403 649Q446 639 483 650Q507 662 516 690Q460 704 398 691Q393 667 403 649Z"/>
</g>
<path d="M276 676Q299 664 338 674M428 674Q461 664 490 674" stroke="#fff1cc" stroke-width="8" stroke-linecap="round" fill="none"/>
<path d="M263 698Q301 708 359 698M406 698Q458 708 503 697" stroke="#ad9270" stroke-width="2" opacity=".58" fill="none"/>
<!-- Rounded sleeves and flared long jacket -->
<path fill="url(#jacket)" d="M306 391Q373 379 459 392Q507 397 539 442L574 492Q584 510 560 534L533 547Q516 551 504 530L488 508L510 572Q515 597 489 608Q383 628 278 605Q251 599 256 573L276 505L254 532Q241 550 220 541L194 522Q179 507 193 485L224 442Q256 402 306 391Z"/>
<path fill="url(#lining)" d="M308 396L365 438L382 485L402 440L462 394L474 423Q426 447 391 502Q341 452 294 427Z"/>
<path fill="#163c51" opacity=".35" d="M384 488L390 495L386 617L378 617Z"/>
<path d="M280 538Q323 545 370 544M399 544Q445 543 489 537M277 553Q324 560 369 557M399 558Q446 557 493 551M200 487L239 520M211 472L251 504M527 511L568 483M521 496L558 469" stroke="#cae7de" stroke-width="7" fill="none" stroke-linecap="round" opacity=".92"/>
<path d="M312 402L361 444M457 402L410 443" fill="none" stroke="#8dbabf" stroke-width="4" stroke-linecap="round"/>
<g fill="#eedbae"><circle cx="357" cy="503" r="5"/><circle cx="414" cy="503" r="5"/><circle cx="354" cy="582" r="5"/><circle cx="414" cy="582" r="5"/></g>
<path fill="none" stroke="#a7dad7" stroke-opacity=".5" stroke-width="3" d="M278 586Q316 600 364 599M397 600Q453 599 488 589"/>
''', {'trouser': ('#83adbf', '#4a7385'), 'sole': ('#f6e8cb', '#c3b191'),
      'sand': ('#ead4a7', '#bfa07a'), 'jacket': ('#89c7d0', '#4d94aa', '#2f6580'),
      'lining': ('#f6f4df', '#c9e4da')})

CITY_OUTFIT = fit_paths('''
<!-- Tapered graphite trousers and conspicuously tall sneakers -->
<path fill="url(#pants)" d="M276 540Q386 521 490 542L481 650Q479 675 453 680H416Q391 675 385 620Q372 675 352 678H304Q281 672 281 650Z"/>
<path d="M307 568Q309 614 317 648M457 567Q456 612 449 648" fill="none" stroke="#66738c" stroke-width="4" opacity=".65"/>
<g fill="url(#shoe)">
 <path d="M296 633Q331 621 367 637L374 680Q383 713 354 721H270Q244 719 244 698Q246 669 282 668Z"/>
 <path d="M402 635Q442 623 476 633L484 668Q519 673 526 696Q526 722 500 722H419Q396 719 395 699Z"/>
</g>
<path d="M249 700Q293 714 371 700L367 712Q353 724 270 721Q253 719 249 710ZM397 702Q471 714 522 700L523 712Q514 725 427 722Q404 721 398 711Z" fill="#b7ccd0"/>
<path d="M301 650L351 657M298 663L352 669M418 657L468 650M419 669L472 663" stroke="#b6c5ef" stroke-width="5" stroke-linecap="round"/>
<!-- Broad quilted bomber with reflective piping and ribbed collar -->
<path fill="url(#bomber)" d="M308 391Q379 380 460 392Q529 390 569 434Q604 470 593 516Q589 538 567 554Q554 567 519 552L509 548L513 567Q516 595 490 605Q381 632 276 605Q252 596 255 571L261 548Q228 567 205 548Q179 532 173 509Q163 477 194 438Q231 393 308 391Z"/>
<path fill="url(#sleeve)" d="M304 395Q255 423 255 523L261 548Q234 569 207 550Q178 533 173 508Q159 472 199 432Q241 395 304 395ZM467 395Q517 420 510 541Q551 571 572 552Q600 533 596 505Q601 470 568 432Q530 394 467 395Z"/>
<path d="M288 415Q267 453 264 503M482 415Q506 449 508 502" stroke="#94a9d5" stroke-width="6" fill="none" stroke-linecap="round"/>
<path d="M184 502Q207 523 245 534M521 534Q560 524 585 504" stroke="#99dbd4" stroke-width="5" fill="none" opacity=".88"/>
<path d="M253 570Q378 601 514 568L514 585Q510 602 489 607Q384 635 277 606Q254 601 253 582Z" fill="#272840"/>
<path d="M278 589Q383 616 490 590" stroke="#637493" stroke-width="3" fill="none"/>
<path d="M320 393Q374 418 385 434Q410 412 453 393L467 408Q415 431 390 458L383 607L373 605L377 454Q345 426 305 407Z" fill="#29283e"/>
<path d="M383 465L380 588" stroke="#98a3bd" stroke-width="4" stroke-dasharray="4 4"/>
<path d="M307 487L341 506M429 506L464 486" stroke="#868dae" stroke-width="5" stroke-linecap="round"/>
<path d="M422 438L449 443L427 460Z" fill="#b7f1d8" opacity=".95"/>
''', {'pants': ('#58617b', '#292d43'), 'shoe': ('#65769d', '#2c3654'),
      'bomber': ('#777399', '#504b75', '#343350'), 'sleeve': ('#736c96', '#49486d', '#31334f')})

MOUNTAIN_OUTFIT = fit_paths('''
<!-- Hiking shorts and lugged high boots -->
<path fill="url(#shorts)" d="M273 542Q385 525 493 544L506 626Q504 651 479 653L413 655Q391 651 383 610Q378 653 352 656L293 655Q268 651 267 627Z"/>
<path fill="#9b9568" d="M276 595L324 592L329 626Q311 643 270 631ZM444 592L495 595L504 631Q469 642 441 627Z"/>
<path d="M281 600L323 597M446 597L492 600" stroke="#d3c994" stroke-width="3"/>
<g fill="#e2dcc1"><path d="M286 650L363 650L362 672L284 671ZM404 650L482 650L483 671L405 672Z"/></g>
<g fill="url(#boot)">
 <path d="M285 653Q325 646 364 655L371 689Q383 708 366 719H258Q234 719 236 696Q245 676 277 677Z"/>
 <path d="M405 655Q446 646 484 653L491 677Q526 679 533 697Q535 718 513 719H407Q390 709 399 690Z"/>
</g>
<path fill="#473b30" d="M237 699L266 706L365 704L374 708L370 721H351L346 726H330L325 721H303L298 726H282L277 721H255L249 726L238 719ZM398 706L500 705L533 699L532 719L521 726L515 721H493L488 726H472L467 721H445L440 726H424L419 721H401Z"/>
<path d="M289 665L348 672M282 676L341 684M421 672L477 665M429 684L487 676" stroke="#d3bd8c" stroke-width="5" stroke-linecap="round"/>
<!-- Boxy, high-hip two-tone windbreaker -->
<path fill="url(#shell)" d="M302 387Q383 375 459 390Q521 396 545 433L574 488Q582 510 566 524L542 540Q521 548 504 521L489 495L502 550Q504 570 481 580Q382 600 279 579Q253 574 258 547L273 497L256 525Q242 546 222 539L194 521Q179 507 191 486L221 430Q252 395 302 387Z"/>
<path fill="url(#yoke)" d="M301 387Q383 375 459 390Q518 395 544 431L554 449L514 475Q488 442 466 447Q423 466 388 473Q347 466 300 447Q276 440 250 475L211 450L223 429Q252 395 301 387Z"/>
<path d="M305 394Q364 422 385 447Q412 418 456 396" stroke="#ece4a9" stroke-width="6" fill="none"/>
<path d="M385 446L385 587" stroke="#3d584d" stroke-width="5"/>
<path d="M385 474L385 514" stroke="#e0b26a" stroke-width="6" stroke-linecap="round"/>
<path d="M282 545Q320 564 360 563M410 563Q455 563 486 545" stroke="#485b4b" stroke-width="4" fill="none"/>
<path d="M282 535Q314 528 354 537L359 560Q320 567 280 551ZM412 537Q450 529 485 535L486 551Q447 565 408 559Z" fill="#96a878"/>
<path d="M208 486L248 514M518 514L557 486" stroke="#c2d2a0" stroke-width="6" fill="none" stroke-linecap="round"/>
<path d="M429 493Q445 477 461 489Q474 500 459 512Q448 520 434 513M437 496Q447 488 457 494Q464 501 455 507" fill="none" stroke="#d8e2b0" stroke-width="3"/>
''', {'shorts': ('#a5a378', '#706b4f'), 'boot': ('#bda17a', '#7c5b3d'),
      'shell': ('#a9bb8c', '#778f66', '#536f59'), 'yoke': ('#e6c79a', '#b89563')})


# Back contours fit behind the same approved inner face. The leaf stems are
# distinct silhouettes attached to the cap/headband rather than repeated decals.
SEA_HEAD_BACK = fit_paths('''
<path fill="url(#rim)" d="M381 112Q473 106 528 176Q563 218 570 275Q585 343 537 381Q491 411 381 411Q273 410 223 374Q180 341 196 269Q215 178 277 137Q319 110 381 112Z"/>
<path fill="url(#fin)" d="M228 222Q205 197 170 205Q149 211 165 236Q169 261 200 280L231 268ZM541 222Q562 198 598 204Q622 212 603 239Q598 263 568 278L540 268Z"/>
<path d="M183 222Q199 225 215 244M583 221Q567 225 552 245" stroke="#e4f5e8" stroke-width="6" fill="none" stroke-linecap="round" opacity=".9"/>
<path fill="url(#leaf)" d="M373 126Q363 93 337 83Q311 78 304 58Q296 40 317 38Q354 36 376 70Q388 88 388 126ZM388 126Q390 90 415 72Q448 49 461 62Q470 74 456 88Q441 103 418 103Q406 103 402 126Z"/>
<ellipse cx="318" cy="55" rx="7" ry="5" fill="#ebf6d5" opacity=".9"/>
''', {'rim': ('#dcf2e8', '#b4d6cb', '#81b2b2'), 'fin': ('#bde5d8', '#73aeb4'),
      'leaf': ('#d7edb1', '#83c8ac', '#428f83')})

SEA_HEAD_FRONT = fit_paths('''
<path fill="url(#cap)" d="M211 169Q213 112 267 89Q320 61 381 98Q412 77 457 87Q526 95 548 155Q537 182 489 184Q353 196 231 182Z"/>
<path fill="#fff9e6" opacity=".63" d="M225 142Q251 94 307 90Q345 85 375 104Q307 100 271 127Q253 139 225 142Z"/>
<path fill="url(#brim)" d="M215 158Q359 134 545 153Q565 158 556 175Q534 198 440 195Q338 181 241 198Q213 200 203 184Q196 170 215 158Z"/>
<path d="M222 165Q370 146 535 160" stroke="#b9e4dd" stroke-width="5" fill="none" stroke-linecap="round"/>
<path d="M287 119Q303 104 319 119Q334 131 350 116" fill="none" stroke="#4c8c9e" stroke-width="6" stroke-linecap="round"/>
<path d="M288 134Q304 119 320 134Q334 146 350 132" fill="none" stroke="#83b8bf" stroke-width="4" stroke-linecap="round"/>
''', {'cap': ('#fff9eb', '#e0eadc', '#bcd5ce'), 'brim': ('#559cad', '#2f657c', '#254a63')})

CITY_HEAD_BACK = fit_paths('''
<path fill="url(#hair)" d="M228 354Q187 340 184 289Q175 238 207 188Q218 143 276 121Q324 94 379 104Q447 66 507 83Q546 96 577 74Q580 109 545 131Q574 169 582 232Q607 304 571 345Q538 404 448 413L301 409Q250 404 228 354Z"/>
<path fill="url(#leaf)" d="M387 111Q388 76 364 62Q334 51 326 33Q317 12 345 18Q377 21 397 47Q409 67 403 103ZM402 110Q420 67 456 66Q483 67 500 49Q501 86 467 98Q444 101 429 112Z"/>
<path d="M343 31Q374 40 389 71M431 91Q464 79 479 77" stroke="#def2bd" stroke-width="4" fill="none" stroke-linecap="round" opacity=".85"/>
''', {'hair': ('#666182', '#47435e', '#342c45'), 'leaf': ('#daf0b9', '#98c9a6', '#4b8f86')})

CITY_HEAD_FRONT = fit_paths('''
<!-- Sculpted side sweep and thick wireless over-ear cups -->
<path fill="url(#sweep)" d="M210 258Q185 205 229 154Q279 96 356 107Q423 64 506 89Q546 104 569 81Q569 132 524 153Q509 184 467 193Q435 200 412 186Q375 212 322 198Q271 183 248 221L229 269Z"/>
<path d="M245 167Q283 119 362 126Q404 102 468 101Q513 105 538 101" stroke="#9c91bc" stroke-width="7" stroke-linecap="round" fill="none" opacity=".65"/>
<path d="M278 185Q315 167 349 178Q388 181 416 157" stroke="#b0a2cb" stroke-width="4" stroke-linecap="round" fill="none" opacity=".34"/>
<path d="M208 251Q201 172 249 139Q273 121 297 119M559 257Q572 181 525 150" fill="none" stroke="#a3adce" stroke-width="13" stroke-linecap="round"/>
<path d="M208 250Q204 179 250 147M561 253Q563 187 534 166" fill="none" stroke="#545678" stroke-width="5" stroke-linecap="round"/>
<g fill="url(#earCup)" stroke="#747c9f" stroke-width="3">
 <path d="M208 232Q228 230 238 253L245 300Q249 325 224 332L196 332Q173 326 170 305L164 269Q163 245 187 237Z"/>
 <path d="M555 232Q532 234 525 256L519 301Q515 326 541 333L569 330Q593 325 597 305L601 267Q601 246 578 238Z"/>
</g>
<path d="M178 267Q180 248 200 245L212 246M588 267Q586 248 566 246L554 246" fill="none" stroke="#a9ecd9" stroke-width="6" stroke-linecap="round"/>
<path d="M185 280L192 307M580 280L573 307" stroke="#8999c5" stroke-width="7" stroke-linecap="round"/>
''', {'sweep': ('#968bad', '#615779', '#38304d'), 'earCup': ('#7186a0', '#4b5578', '#323951')})

MOUNTAIN_HEAD_BACK = fit_paths('''
<path fill="url(#rim)" d="M381 114Q481 105 539 179Q584 229 577 313Q567 390 464 409H312Q226 403 202 347Q177 292 205 234Q218 175 271 140Q319 111 381 114Z"/>
<path fill="url(#leaf)" d="M370 128Q357 104 331 99Q295 93 293 68Q287 43 307 45Q350 47 370 78Q384 98 389 128ZM387 128Q387 99 407 76Q429 46 465 42Q485 41 479 66Q474 88 441 95Q414 101 405 129Z"/>
<path d="M307 62Q328 68 351 89M466 60Q443 65 424 88" stroke="#edfacf" stroke-width="5" fill="none" stroke-linecap="round" opacity=".8"/>
''', {'rim': ('#b5c1a4', '#7d9273', '#5f755e'), 'leaf': ('#d2eaa7', '#91c78b', '#57956a')})

MOUNTAIN_HEAD_FRONT = fit_paths('''
<!-- Knit cap, earflaps, beanie seam and trail badge -->
<path fill="url(#earFlap)" d="M219 164Q198 182 198 217Q181 242 183 282Q179 302 151 321Q181 334 211 319Q235 307 241 273L252 199ZM542 165Q563 185 564 217Q581 242 579 282Q583 302 611 321Q581 334 551 319Q527 307 521 273L511 199Z"/>
<path d="M205 229Q208 285 177 315M556 229Q553 285 584 315" stroke="#e3b879" stroke-width="6" stroke-linecap="round" fill="none" opacity=".72"/>
<path fill="url(#knit)" d="M205 182Q208 121 249 96Q293 58 357 83Q390 67 441 76Q529 76 557 158L561 181Q529 211 381 205Q250 210 205 182Z"/>
<path d="M226 159Q229 120 264 102M259 149Q264 102 290 92M301 141Q306 105 319 86M347 143L354 88M394 143L399 82M444 141L445 87M485 145Q483 104 473 91M526 155Q523 125 509 113" stroke="#e8c080" stroke-width="4" stroke-linecap="round" fill="none" opacity=".66"/>
<path fill="url(#rib)" d="M202 154Q377 129 559 154Q573 160 568 176L559 198Q548 211 527 210Q380 190 235 211Q211 209 204 196L194 176Q190 160 202 154Z"/>
<path d="M215 166L223 196M237 164L244 196M259 161L266 193M282 158L288 191M305 157L309 190M327 156L330 189M349 155L350 188M371 155L371 188M393 155L391 188M415 155L412 189M437 156L433 190M459 158L454 192M481 160L475 194M503 161L497 196M525 164L518 198M547 166L540 199" stroke="#a36f3a" stroke-width="3" stroke-linecap="round" opacity=".66"/>
<path d="M353 166Q382 159 409 166L409 193Q382 200 353 193Z" fill="#f0d7a8" stroke="#a8794e" stroke-width="2"/>
<path d="M360 188L372 174L379 183L387 171L402 188" fill="none" stroke="#7a815b" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
''', {'earFlap': ('#c5a06e', '#9d6f48', '#765737'), 'knit': ('#e3b97c', '#c28a50', '#a77440'),
      'rib': ('#e8bc78', '#cc9555', '#bc854b')})


def eyes(left_shape: str, right_shape: str, iris: tuple[str, ...], features: str,
         *, iris_rx: int, iris_ry: int, iris_y: int = 276) -> str:
    defs = gradient('iris', *iris) + f'''
    <clipPath id="left-eye"><path d="{left_shape}"/></clipPath>
    <clipPath id="right-eye"><path d="{right_shape}"/></clipPath>
    '''
    eyes_markup = f'<g fill="#fff7eb" stroke="#664234" stroke-width="3.5" stroke-linejoin="round"><path d="{left_shape}"/><path d="{right_shape}"/></g>'
    for center, eye in ((319, 'left-eye'), (462, 'right-eye')):
        eyes_markup += f'''
        <g clip-path="url(#{eye})">
         <ellipse cx="{center}" cy="{iris_y}" rx="{iris_rx}" ry="{iris_ry}" fill="url(#iris)" stroke="#4b3633" stroke-width="2"/>
         <ellipse cx="{center + 2}" cy="{iris_y - 1}" rx="{iris_rx * .52}" ry="{iris_ry * .58}" fill="#241e25" opacity=".83"/>
         <ellipse cx="{center + 8}" cy="{iris_y - 9}" rx="6" ry="5.5" fill="#fff7ed"/>
         <ellipse cx="{center - 7}" cy="{iris_y + 8}" rx="3" ry="2.5" fill="#fff3dc" opacity=".68"/>
        </g>'''
    return svg(eyes_markup + features, defs)


SEA_EYES = eyes(
    'M277 273Q290 250 321 250Q348 249 359 269Q346 290 318 292Q290 293 277 273Z',
    'M421 269Q432 249 461 250Q491 250 503 272Q489 292 461 292Q434 290 421 269Z',
    ('#3c3b39', '#70624f', '#a39b77'), '''
    <path d="M285 230Q313 219 337 230M443 230Q469 219 495 232" fill="none" stroke="#8a5b48" stroke-width="5.5" stroke-linecap="round"/>
    <path d="M365 328Q390 349 417 326" fill="none" stroke="#965140" stroke-width="6" stroke-linecap="round"/>
    ''', iris_rx=19, iris_ry=22, iris_y=272)

CITY_EYES = eyes(
    'M273 277Q286 246 313 247Q339 248 362 268Q345 290 319 296Q290 298 273 277Z',
    'M418 268Q440 246 466 245Q490 244 507 273Q492 297 461 296Q436 291 418 268Z',
    ('#42405c', '#5e5778', '#a397cb'), '''
    <path d="M280 227Q309 207 337 220M439 228Q465 232 490 218" fill="none" stroke="#785546" stroke-width="7" stroke-linecap="round"/>
    <path d="M367 330Q390 342 419 320" fill="none" stroke="#975449" stroke-width="6" stroke-linecap="round"/>
    ''', iris_rx=22, iris_ry=28, iris_y=274)

MOUNTAIN_EYES = eyes(
    'M271 279Q274 247 295 237Q323 220 347 240Q367 257 362 287Q353 309 322 313Q292 315 276 295Z',
    'M418 286Q413 257 432 239Q457 220 482 237Q504 246 509 277Q506 309 471 313Q433 315 418 286Z',
    ('#4c372c', '#79583d', '#be945b'), '''
    <path d="M282 225Q305 207 333 216M446 216Q472 205 494 225" fill="none" stroke="#835948" stroke-width="6.5" stroke-linecap="round"/>
    <path d="M351 326Q360 315 373 321Q393 329 410 321Q424 315 432 325Q430 357 393 361Q357 358 351 326Z" fill="#853c34"/>
    <path d="M363 347Q389 329 421 345Q410 359 393 359Q375 358 363 347Z" fill="#de8875"/>
    ''', iris_rx=23, iris_ry=31, iris_y=274)


SEA_PROP = fit_paths('''
<path d="M313 402Q342 433 388 483L491 546" stroke="#244f64" stroke-width="21" stroke-linecap="round" fill="none"/>
<path d="M312 401Q344 434 388 482L490 544" stroke="#adcbb9" stroke-width="13" stroke-linecap="round" fill="none"/>
<path fill="url(#pouch)" stroke="#96795e" stroke-width="2" d="M447 534Q452 508 477 504Q503 504 521 527Q544 544 548 569Q538 592 505 607Q465 607 445 584Q432 562 447 534Z"/>
<path d="M469 525Q453 545 456 570Q460 583 481 592M482 519Q473 552 488 591M493 521Q494 558 503 593M506 529Q518 557 518 584M516 541Q534 556 534 570" stroke="#ab8b6c" stroke-width="4" stroke-linecap="round" fill="none" opacity=".83"/>
<path d="M447 575Q488 586 545 566Q545 582 527 596Q488 624 456 590Z" fill="url(#seam)"/>
<path d="M470 586Q498 594 532 578" stroke="#f5ebcf" stroke-width="3" fill="none" opacity=".85"/>
''', {'pouch': ('#f7e2b6', '#e1bf97', '#c79e78'), 'seam': ('#d5c09a', '#a99277')})

CITY_PROP = fit_paths('''
<path d="M459 396Q418 448 369 480L297 534" stroke="#272b43" stroke-width="24" stroke-linecap="round" fill="none"/>
<path d="M459 396Q419 447 369 480L297 534" stroke="#8b91ac" stroke-width="13" stroke-linecap="round" fill="none"/>
<path d="M415 453L393 468" stroke="#caf6e5" stroke-width="7" stroke-linecap="round"/>
<path fill="url(#satchel)" stroke="#36374e" stroke-width="4" d="M234 517L334 499Q353 498 363 517L374 566Q380 587 359 595L255 612Q231 611 222 591L208 549Q203 526 234 517Z"/>
<path fill="url(#lid)" d="M223 521L336 503Q352 502 360 518L367 545L263 566Q229 569 213 544Q209 529 223 521Z"/>
<path d="M246 578L345 560L350 579L253 598Z" fill="#292d4a"/>
<path d="M236 534L335 515" stroke="#c0d9f0" stroke-width="5" stroke-linecap="round"/>
<path d="M258 587L270 585M280 583L293 581M302 579L314 577" stroke="#a1e9d5" stroke-width="5" stroke-linecap="round"/>
<path d="M322 542L338 539L341 551L325 555Z" fill="#d5abc7"/>
''', {'satchel': ('#687293', '#3f466b', '#2e314e'), 'lid': ('#8695b5', '#626b8e')})

MOUNTAIN_PROP_BACK = fit_paths('''
<path fill="url(#pack)" d="M230 383Q272 368 313 392L324 451L447 443L459 391Q503 368 542 384Q570 396 585 432Q615 483 604 537Q600 560 572 567L202 568Q166 563 157 529Q146 476 169 425Q185 397 230 383Z"/>
<path fill="url(#roll)" d="M204 384Q298 355 326 382Q335 399 321 414Q267 423 214 433Q187 432 181 408Q180 391 204 384Z"/>
<path fill="url(#roll)" d="M447 384Q481 358 553 382Q573 391 574 407Q573 427 553 431Q505 421 450 416Q431 407 447 384Z"/>
<path d="M184 465Q170 505 189 540M585 468Q600 505 582 544" stroke="#d0bf87" stroke-width="6" fill="none" stroke-linecap="round"/>
''', {'pack': ('#b39366', '#8e7850', '#5e6042'), 'roll': ('#e0bf83', '#aa925f')})

MOUNTAIN_PROP = fit_paths('''
<path d="M302 398Q275 444 297 535M465 398Q491 447 466 535" stroke="#5e6549" stroke-width="33" stroke-linecap="round" fill="none"/>
<path d="M303 400Q277 444 297 535M464 400Q489 447 467 535" stroke="#d0a369" stroke-width="23" stroke-linecap="round" fill="none"/>
<path d="M298 408Q280 448 291 498M470 408Q484 447 473 498" stroke="#f0c88b" stroke-width="4" stroke-linecap="round" fill="none"/>
<path d="M293 477Q378 499 472 477" stroke="#646044" stroke-width="14" fill="none"/>
<rect x="371" y="481" width="36" height="20" rx="5" fill="#eed5a0" stroke="#61583f" stroke-width="3"/>
<path d="M389 485L389 497" stroke="#766646" stroke-width="3"/>
<path fill="url(#bottle)" stroke="#526c57" stroke-width="2" d="M553 527L568 513L591 520L600 538L594 574Q588 588 572 584L552 579Q537 573 540 556Z"/>
<path d="M571 510L574 500L596 507L592 522Z" fill="#717b62"/>
<path d="M549 550Q572 560 596 561" stroke="#e3e8ba" stroke-width="6" fill="none"/>
''', {'bottle': ('#a9c7a1', '#769a7e', '#56795d')})

# These masks reuse approved pixels only in the exposed inner face and hands.
FACE_MASK = svg('''
<path fill="white" d="M387 153C454 152 514 204 529 268C550 348 506 393 408 398C302 405 232 366 231 303C230 232 289 170 353 157Q366 153 387 153Z"/>
''')
HANDS_MASK = svg('''
<path fill="white" d="M218 499Q226 511 252 532Q241 565 215 566Q183 570 186 537Q189 521 218 499ZM550 498Q575 517 581 535Q585 567 552 567Q528 564 512 534Q536 514 550 498Z"/>
''')

VECTORS = {
    'sea-outfit': SEA_OUTFIT, 'sea-head-back': SEA_HEAD_BACK,
    'sea-head-front': SEA_HEAD_FRONT, 'sea-eyes': SEA_EYES, 'sea-prop-front': SEA_PROP,
    'city-outfit': CITY_OUTFIT, 'city-head-back': CITY_HEAD_BACK,
    'city-head-front': CITY_HEAD_FRONT, 'city-eyes': CITY_EYES, 'city-prop-front': CITY_PROP,
    'mountain-outfit': MOUNTAIN_OUTFIT, 'mountain-head-back': MOUNTAIN_HEAD_BACK,
    'mountain-head-front': MOUNTAIN_HEAD_FRONT, 'mountain-eyes': MOUNTAIN_EYES,
    'mountain-prop-back': MOUNTAIN_PROP_BACK, 'mountain-prop-front': MOUNTAIN_PROP,
    'face-mask': FACE_MASK, 'hands-mask': HANDS_MASK,
}


def rasterize(vectors: dict[str, str]) -> dict[str, Image.Image]:
    """Capture one transparent local SVG atlas with a fresh Chrome profile."""
    columns = 5
    width = columns * SIZE
    height = ((len(vectors) + columns - 1) // columns) * SIZE
    tiles = []
    boxes = {}
    for index, (name, source) in enumerate(vectors.items()):
        x, y = (index % columns) * SIZE, (index // columns) * SIZE
        prefix = f'tile{index}-'
        tile = source.replace('id="', f'id="{prefix}').replace('url(#', f'url(#{prefix}')
        tiles.append(tile.replace('<svg ', f'<svg x="{x}" y="{y}" ', 1))
        boxes[name] = (x, y, x + SIZE, y + SIZE)
    with tempfile.TemporaryDirectory(prefix='nunti-skin-svg-') as temp:
        directory = Path(temp)
        atlas = directory / 'atlas.svg'
        screenshot = directory / 'atlas.png'
        atlas.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">' + ''.join(tiles) + '</svg>')
        result = subprocess.run([
            str(CHROME), '--headless', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
            '--disable-background-networking', '--disable-component-update', '--disable-sync',
            '--no-first-run', '--host-resolver-rules=MAP * ~NOTFOUND',
            '--default-background-color=00000000', '--force-device-scale-factor=1',
            f'--user-data-dir={directory / "chrome"}', f'--window-size={width},{height}',
            f'--screenshot={screenshot}', atlas.as_uri(),
        ], check=False, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f'Local SVG rasterizer failed ({result.returncode}): {result.stderr}')
        atlas_image = Image.open(screenshot)
        assert atlas_image.mode == 'RGBA' and atlas_image.size == (width, height), atlas_image.size
        assert atlas_image.getpixel((0, 0)) == (0, 0, 0, 0)
        images = {name: atlas_image.crop(box) for name, box in boxes.items()}
        assert all(image.getchannel('A').getbbox() for image in images.values())
        return images


def rgba(path: Path) -> Image.Image:
    return Image.open(path).convert('RGBA')


def composite(*images: Image.Image) -> Image.Image:
    result = Image.new('RGBA', (SIZE, SIZE))
    for image in images:
        result.alpha_composite(image)
    return result


def apply_mask(image: Image.Image, mask: Image.Image) -> Image.Image:
    result = image.copy()
    result.putalpha(ImageChops.multiply(result.getchannel('A'), mask))
    return result


def save(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_comparison(finals: dict[str, Image.Image]) -> None:
    """Unlabeled grayscale at inspection and thumbnail size, plus color reference."""
    for gray in (False, True):
        board = Image.new('RGB', (1224, 430), '#f3f2eb' if not gray else '#eeeeee')
        draw = ImageDraw.Draw(board)
        for index, image in enumerate(finals.values()):
            x = index * 300 + 12
            draw.rounded_rectangle((x, 12, x + 288, 335), 20, fill='#fffcf3' if not gray else '#fafafa')
            for size, offset in ((288, (x, 20)), (64, (x + 112, 351))):
                resampled = image.resize((size, size), Image.Resampling.LANCZOS)
                if gray:
                    alpha = resampled.getchannel('A')
                    resampled = ImageOps.grayscale(resampled).convert('RGBA')
                    resampled.putalpha(alpha)
                board.paste(resampled, offset, resampled)
        save(board, OUT / ('comparison-grayscale.png' if gray else 'comparison-color.png'))


def main() -> None:
    layers = rasterize(VECTORS)
    base = rgba(SOURCE / 'base.png')
    shared_face = apply_mask(rgba(SOURCE / 'core/head.png'), layers['face-mask'].getchannel('A'))
    shared_hands = apply_mask(base, layers['hands-mask'].getchannel('A'))
    vector_path = OUT / 'vectors'
    vector_path.mkdir(parents=True, exist_ok=True)
    for name, source in VECTORS.items():
        (vector_path / f'{name}.svg').write_text(source)
    save(shared_face, vector_path / 'shared-face.png')
    save(shared_hands, vector_path / 'shared-hands.png')

    def core(name: str) -> Image.Image:
        return rgba(SOURCE / f'core/{name}.png')

    default = {
        'outfit': composite(core('body'), core('scarf')),
        'head': composite(core('head'), core('sprout')),
        'eyes': rgba(SOURCE / 'expressions/base.png'),
        'accessory': composite(core('bag'), core('badge')),
    }
    finals = {}
    files = {}
    for skin_id in ('default', *SKINS):
        if skin_id == 'default':
            parts = default
        else:
            outfit = composite(shared_hands, layers[f'{skin_id}-outfit'])
            head = composite(layers[f'{skin_id}-head-back'], shared_face, layers[f'{skin_id}-head-front'])
            prop_front = layers[f'{skin_id}-prop-front']
            if skin_id == 'mountain':
                # Preserve visible rear contour in an independently timed layer.
                occluders = composite(outfit, head).getchannel('A')
                prop_back = apply_mask(layers['mountain-prop-back'], ImageChops.invert(occluders))
                prop_front = composite(prop_back, prop_front)
            parts = {'outfit': outfit, 'head': head, 'eyes': layers[f'{skin_id}-eyes'], 'accessory': prop_front}
        final = composite(*(parts[part] for part in ORDER))
        if skin_id == 'default':
            assert final.tobytes() == composite(base).tobytes(), 'Approved default assembly changed visible pixels'
        finals[skin_id] = final
        for name, image in (*parts.items(), ('final', final)):
            asset = f'{skin_id}/{name}.png'
            path = OUT / asset
            if skin_id == 'default' and name == 'final':
                path.write_bytes((SOURCE / 'base.png').read_bytes())
            else:
                save(image, path)
            alpha = image.getchannel('A')
            assert alpha.getextrema() == (0, 255)
            files[asset] = {'sha256': digest(path), 'alphaBounds': alpha.getbbox(), 'bytes': path.stat().st_size}
    make_comparison(finals)
    manifest = {
        'assetVersion': 'skin-v2',
        'status': 'ART_DIRECTION_NOT_FINAL',
        'canvas': [SIZE, SIZE],
        'order': ORDER,
        'owner': 'NUNTI project',
        'source': str(SOURCE.relative_to(ROOT)),
        'sourceSha256': digest(SOURCE / 'base.png'),
        'licensingNote': 'Local vector artwork authored for NUNTI. Approved A base/inner face/hands reused from the project; original rights record not independently verified.',
        'generation': 'Hand-authored SVG paths, local Chrome rasterization at 1×, Pillow RGBA composition. Zero generation API calls.',
        'builder': 'scripts/build_nunti_skin_v2_assets.py',
        'fallback': 'default/final.png',
        'notes': 'Default body is segmented from approved raster artwork. New outfits, headgear, eyes and props are independent vector sources and registered transparent runtime layers. Shared approved raster face and hands are composited into head/outfit. Back pack contour is masked against head and outfit.',
        'files': files,
    }
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Compiled {len(files)} registered RGBA assets; approved default pixels match exactly.')


if __name__ == '__main__':
    main()
